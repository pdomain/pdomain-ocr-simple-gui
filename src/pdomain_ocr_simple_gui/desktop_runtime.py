"""Desktop lifecycle runtime state and browser-session coordination."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, final
from uuid import uuid4

from starlette.responses import PlainTextResponse

from pdomain_ocr_simple_gui.instance import InstanceRecord, InstanceReply
from pdomain_ocr_simple_gui.lifecycle import ConnectionLease, LifecycleController, LifecycleRejectedError

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


SESSION_COOKIE_NAME = "pdomain_lifecycle_session"


@dataclass(frozen=True)
class ShowRequest:
    """A native request for a browser page to become visible."""

    request_id: str


@dataclass(frozen=True)
class BrowserSession:
    """An active browser page with a server-owned connection lease."""

    lease: ConnectionLease
    messages: asyncio.Queue[ShowRequest]


@dataclass(frozen=True)
class _PendingShow:
    """One native show request waiting for a visible-browser acknowledgment."""

    request_id: str
    target: BrowserSession
    acknowledged: asyncio.Event


@final
class DesktopRuntime:
    """Hold desktop instance identity, browser sessions, and lifecycle state."""

    def __init__(self, record: InstanceRecord, controller: LifecycleController) -> None:
        if record.instance_id != controller.instance_id:
            raise ValueError("desktop runtime record and lifecycle controller have different instance IDs")
        self._record = record
        self._controller = controller
        self._session_secret = secrets.token_urlsafe(32)
        self._sessions: dict[str, BrowserSession] = {}
        self._session_lock = asyncio.Lock()
        self._show_lock = asyncio.Lock()
        self._pending_show: _PendingShow | None = None

    @property
    def record(self) -> InstanceRecord:
        """Return the current desktop instance record."""
        return self._record

    @property
    def controller(self) -> LifecycleController:
        """Return the server-owned lifecycle controller."""
        return self._controller

    @property
    def session_cookie(self) -> str:
        """Return the opaque value used only in the HttpOnly session cookie."""
        return self._session_secret

    def same_browser_origin(self, origin: str | None, host: str | None) -> bool:
        """Return whether browser headers name this instance's exact loopback origin."""
        return origin == self._record.origin and host == self._record.origin.removeprefix("http://")

    def valid_browser_session(self, origin: str | None, host: str | None, cookie: str | None) -> bool:
        """Return whether a browser request has the private lifecycle session."""
        return (
            self.same_browser_origin(origin, host)
            and cookie is not None
            and secrets.compare_digest(cookie, self._session_secret)
        )

    def native_challenge(self, authorization: str | None, challenge: str | None) -> str | None:
        """Return a verified native challenge, or ``None`` for an invalid request."""
        if challenge is None or not challenge:
            return None
        expected = f"Bearer {self._record.capability.get_secret_value()}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            return None
        return challenge

    def instance_reply(self, challenge: str, *, accepted: bool, message: str = "") -> InstanceReply:
        """Build a native response from the controller's consistent snapshot."""
        snapshot = self._controller.snapshot()
        return InstanceReply(
            app_id=self._record.app_id,
            instance_id=self._record.instance_id,
            challenge=challenge,
            accepted=accepted,
            message=message,
            live_tabs=len(snapshot.active_leases),
            active_operations=snapshot.activity_count,
        )

    async def attach_browser(self, instance_id: str, page_id: str) -> BrowserSession:
        """Attach a browser page and supersede a prior connection for that page."""
        async with self._session_lock:
            lease = self._controller.attach(instance_id, page_id)
            session = BrowserSession(lease=lease, messages=asyncio.Queue())
            _ = self._sessions.pop(page_id, None)
            self._sessions[page_id] = session
            return session

    async def detach_browser(self, session: BrowserSession) -> bool:
        """Detach a browser only when it remains the current page connection."""
        async with self._session_lock:
            if self._sessions.get(session.lease.page_id) != session:
                return False
            del self._sessions[session.lease.page_id]
            return self._controller.detach(session.lease)

    async def request_show(self, *, timeout_seconds: float = 1.0) -> bool:
        """Ask live browser pages to show themselves and await a visible-page ack."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        async with self._show_lock:
            async with self._session_lock:
                if not self._sessions:
                    return False
                target = next(reversed(self._sessions.values()))
                pending = _PendingShow(uuid4().hex, target, asyncio.Event())
                self._pending_show = pending
                target.messages.put_nowait(ShowRequest(pending.request_id))
            try:
                _ = await asyncio.wait_for(pending.acknowledged.wait(), timeout=timeout_seconds)
            except TimeoutError:
                return False
            else:
                return True
            finally:
                async with self._session_lock:
                    if self._pending_show == pending:
                        self._pending_show = None

    async def acknowledge_show(self, session: BrowserSession, request_id: str) -> bool:
        """Acknowledge a show request from the current browser connection only."""
        async with self._session_lock:
            pending = self._pending_show
            if (
                self._sessions.get(session.lease.page_id) != session
                or pending is None
                or pending.target != session
                or pending.request_id != request_id
            ):
                return False
            _ = pending.acknowledged.set()
            return True

    async def monitor(self, stop_event: asyncio.Event, *, interval_seconds: float = 1.0) -> None:
        """Evaluate automatic shutdown until the server exits or monitoring stops."""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        while not stop_event.is_set():
            if self._controller.evaluate():
                return
            try:
                _ = await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                continue


def _runtime_from_scope(scope: Scope) -> DesktopRuntime | None:
    app = scope.get("app")
    state = getattr(app, "state", None)
    runtime = getattr(state, "desktop_runtime", None)
    if isinstance(runtime, DesktopRuntime):
        return runtime
    return None


@final
class LifecycleActivityMiddleware:
    """Keep non-lifecycle API work alive until the ASGI response fully completes."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Guard a complete non-lifecycle API request with an activity token."""
        path = scope.get("path")
        if (
            scope["type"] != "http"
            or not isinstance(path, str)
            or not path.startswith("/api/")
            or path.startswith("/api/lifecycle")
        ):
            await self._app(scope, receive, send)
            return
        runtime = _runtime_from_scope(scope)
        if runtime is None:
            await self._app(scope, receive, send)
            return
        try:
            token = runtime.controller.begin_activity(runtime.record.instance_id, "api_request")
        except LifecycleRejectedError:
            response = PlainTextResponse("server shutdown is in progress", status_code=503)
            await response(scope, receive, send)
            return
        try:
            await self._app(scope, receive, send)
        finally:
            _ = runtime.controller.end_activity(token)


__all__ = (
    "SESSION_COOKIE_NAME",
    "BrowserSession",
    "DesktopRuntime",
    "LifecycleActivityMiddleware",
    "ShowRequest",
)
