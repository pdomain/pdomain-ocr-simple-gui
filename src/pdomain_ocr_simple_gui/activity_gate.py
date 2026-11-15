"""Keep app storage operations separate from an exclusive migration."""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import TYPE_CHECKING, final

from starlette.responses import PlainTextResponse

if TYPE_CHECKING:
    from collections.abc import Generator

    from starlette.types import ASGIApp, Receive, Scope, Send


class StorageBusyError(RuntimeError):
    """Raised when app work and a storage migration overlap."""


@final
class StorageGate:
    """Track complete requests and reserve migration without waiting on work."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._active = 0
        self._migrating = False

    @property
    def active_count(self) -> int:
        """Return the number of requests whose work is not complete."""
        with self._lock:
            return self._active

    @property
    def migrating(self) -> bool:
        """Return whether migration owns storage access."""
        with self._lock:
            return self._migrating

    @contextmanager
    def activity(self) -> Generator[None]:
        """Hold an activity reservation through response and background work."""
        with self._lock:
            if self._migrating:
                raise StorageBusyError("A data migration is in progress")
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    @contextmanager
    def exclusive(self) -> Generator[None]:
        """Reserve migration only when all other app work has finished."""
        with self._lock:
            if self._active or self._migrating:
                raise StorageBusyError("Wait for current work or migration to finish")
            self._migrating = True
        try:
            yield
        finally:
            with self._lock:
                self._migrating = False


@final
class StorageActivityMiddleware:
    """Retain storage reservations through the entire ASGI response lifetime."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Guard app work until its response and background work complete."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        path: object = scope.get("path")
        app: object = scope.get("app")
        state: object = getattr(app, "state", None)
        gate: object = getattr(state, "storage_gate", None)
        if (
            not isinstance(gate, StorageGate)
            or not isinstance(path, str)
            or not path.startswith("/api/")
            or path.startswith(("/api/locations", "/api/lifecycle"))
        ):
            await self._app(scope, receive, send)
            return
        try:
            with gate.activity():
                await self._app(scope, receive, send)
        except StorageBusyError as exc:
            await PlainTextResponse(str(exc), status_code=409)(scope, receive, send)
