"""Server-owned browser leases and graceful shutdown decisions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING, final
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable


class ShutdownState(StrEnum):
    """The lifecycle controller's exit state."""

    RUNNING = "running"
    EXIT_REQUESTED = "exit_requested"


class ExitReason(StrEnum):
    """Reasons the server can begin graceful shutdown."""

    INITIAL_GRACE_EXPIRED = "initial_grace_expired"
    LAST_TAB_GRACE_EXPIRED = "last_tab_grace_expired"
    USER_QUIT = "user_quit"


class LifecycleRejectedError(RuntimeError):
    """Raised when shutdown has started."""


class WrongInstanceError(LifecycleRejectedError):
    """Raised when a prior server instance sends a lifecycle command."""


@dataclass(frozen=True)
class ConnectionLease:
    """A browser connection generation for one loaded page."""

    instance_id: str
    page_id: str
    generation: int


@dataclass(frozen=True)
class ActivityToken:
    """A server-side operation that defers automatic exit."""

    instance_id: str
    token_id: str
    kind: str


@dataclass(frozen=True)
class QuitPreparation:
    """The confirmation state for a user-initiated quit."""

    other_tab_count: int
    active_activity_count: int
    can_quit: bool


@dataclass(frozen=True)
class QuitRequestResult:
    """The outcome of a user-initiated quit request."""

    accepted: bool
    other_tab_count: int
    active_activity_count: int


@dataclass(frozen=True)
class LifecycleSnapshot:
    """A route-safe view of lifecycle state."""

    instance_id: str
    active_leases: tuple[ConnectionLease, ...]
    activity_kinds: tuple[str, ...]
    activity_count: int
    shutdown_state: ShutdownState
    shutdown_reason: ExitReason | None
    shutdown_deadline: float | None
    has_seen_connection: bool
    persistent: bool
    keep_running: bool


@final
class LifecycleController:
    """Coordinate browser connections, active work, and graceful exit."""

    def __init__(
        self,
        instance_id: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        request_exit: Callable[[], None],
        initial_grace_seconds: float = 120.0,
        last_tab_grace_seconds: float = 30.0,
        persistent: bool = False,
        keep_running: bool = False,
    ) -> None:
        if not instance_id:
            raise ValueError("instance_id must not be empty")
        if initial_grace_seconds < 0:
            raise ValueError("initial_grace_seconds must not be negative")
        if last_tab_grace_seconds < 0:
            raise ValueError("last_tab_grace_seconds must not be negative")

        self._instance_id = instance_id
        self._clock = clock
        self._request_exit = request_exit
        self._initial_grace_seconds = initial_grace_seconds
        self._last_tab_grace_seconds = last_tab_grace_seconds
        self._persistent = persistent
        self._keep_running = keep_running
        self._lock = RLock()
        self._leases: dict[str, ConnectionLease] = {}
        self._next_generation: dict[str, int] = {}
        self._activities: dict[str, ActivityToken] = {}
        self._has_seen_connection = False
        self._shutdown_state = ShutdownState.RUNNING
        self._shutdown_reason: ExitReason | None = None
        self._shutdown_deadline = self._automatic_deadline_after(self._clock())

    @property
    def instance_id(self) -> str:
        """Return the server instance ID accepted by this controller."""
        return self._instance_id

    def attach(self, instance_id: str, page_id: str) -> ConnectionLease:
        """Register a fresh browser connection for a loaded page."""
        if not page_id:
            raise ValueError("page_id must not be empty")

        with self._lock:
            self._require_current_instance(instance_id)
            self._require_running()
            generation = self._next_generation.get(page_id, 0) + 1
            self._next_generation[page_id] = generation
            lease = ConnectionLease(self._instance_id, page_id, generation)
            self._leases[page_id] = lease
            self._has_seen_connection = True
            self._shutdown_deadline = None
            return lease

    def detach(self, lease: ConnectionLease) -> bool:
        """Remove a connection only when it is the current page generation."""
        with self._lock:
            if lease.instance_id != self._instance_id:
                return False
            if self._leases.get(lease.page_id) != lease:
                return False
            del self._leases[lease.page_id]
            if not self._leases:
                self._shutdown_deadline = self._automatic_deadline_after(self._clock())
            return True

    def begin_activity(self, instance_id: str, kind: str) -> ActivityToken:
        """Register work that must finish before automatic exit."""
        if not kind:
            raise ValueError("kind must not be empty")

        with self._lock:
            self._require_current_instance(instance_id)
            self._require_running()
            token = ActivityToken(self._instance_id, uuid4().hex, kind)
            self._activities[token.token_id] = token
            return token

    def end_activity(self, token: ActivityToken) -> bool:
        """Release an activity token once its operation completes."""
        with self._lock:
            if token.instance_id != self._instance_id:
                return False
            if self._activities.get(token.token_id) != token:
                return False
            del self._activities[token.token_id]
            return True

    def set_persistent(self, persistent: bool) -> None:
        """Set whether this explicit headless instance is persistent."""
        with self._lock:
            self._persistent = persistent
            self._refresh_deadline()

    def set_keep_running(self, keep_running: bool) -> None:
        """Set the desktop keep-running preference."""
        with self._lock:
            self._keep_running = keep_running
            self._refresh_deadline()

    def prepare_quit(self, *, caller_page_id: str | None = None) -> QuitPreparation:
        """Report whether a user quit needs confirmation or must wait for work."""
        with self._lock:
            return self._quit_preparation(caller_page_id)

    def request_quit(
        self, *, confirm_other_tabs: bool, caller_page_id: str | None = None
    ) -> QuitRequestResult:
        """Request graceful exit after the caller confirms other live tabs."""
        with self._lock:
            preparation = self._quit_preparation(caller_page_id)
            if preparation.active_activity_count or (preparation.other_tab_count and not confirm_other_tabs):
                return QuitRequestResult(
                    accepted=False,
                    other_tab_count=preparation.other_tab_count,
                    active_activity_count=preparation.active_activity_count,
                )
            if self._shutdown_state is ShutdownState.EXIT_REQUESTED:
                return QuitRequestResult(
                    accepted=False,
                    other_tab_count=preparation.other_tab_count,
                    active_activity_count=preparation.active_activity_count,
                )
            self._select_exit(ExitReason.USER_QUIT)

        self._request_exit()
        return QuitRequestResult(
            accepted=True,
            other_tab_count=preparation.other_tab_count,
            active_activity_count=preparation.active_activity_count,
        )

    def evaluate(self) -> bool:
        """Request graceful exit if the current automatic deadline has passed."""
        with self._lock:
            reason = self._automatic_exit_reason()
            if reason is None:
                return False
            self._select_exit(reason)

        self._request_exit()
        return True

    def snapshot(self) -> LifecycleSnapshot:
        """Return a consistent lifecycle view for routes and diagnostics."""
        with self._lock:
            return LifecycleSnapshot(
                instance_id=self._instance_id,
                active_leases=tuple(sorted(self._leases.values(), key=lambda lease: lease.page_id)),
                activity_kinds=tuple(sorted(token.kind for token in self._activities.values())),
                activity_count=len(self._activities),
                shutdown_state=self._shutdown_state,
                shutdown_reason=self._shutdown_reason,
                shutdown_deadline=self._shutdown_deadline,
                has_seen_connection=self._has_seen_connection,
                persistent=self._persistent,
                keep_running=self._keep_running,
            )

    def _require_current_instance(self, instance_id: str) -> None:
        if instance_id != self._instance_id:
            raise WrongInstanceError("lifecycle command belongs to a different server instance")

    def _require_running(self) -> None:
        if self._shutdown_state is ShutdownState.EXIT_REQUESTED:
            raise LifecycleRejectedError("server shutdown has already been requested")

    def _quit_preparation(self, caller_page_id: str | None) -> QuitPreparation:
        if caller_page_id is not None and caller_page_id not in self._leases:
            raise LifecycleRejectedError(
                "The requesting browser page is not connected; reconnect before quitting"
            )
        other_tab_count = len(self._leases) - (1 if caller_page_id is not None else 0)
        activity_count = len(self._activities)
        return QuitPreparation(
            other_tab_count=other_tab_count,
            active_activity_count=activity_count,
            can_quit=(
                self._shutdown_state is ShutdownState.RUNNING and activity_count == 0 and other_tab_count == 0
            ),
        )

    def _automatic_exit_reason(self) -> ExitReason | None:
        if self._shutdown_state is ShutdownState.EXIT_REQUESTED:
            return None
        if self._automatic_shutdown_disabled() or self._leases or self._activities:
            return None
        if self._shutdown_deadline is None or self._clock() < self._shutdown_deadline:
            return None
        if self._has_seen_connection:
            return ExitReason.LAST_TAB_GRACE_EXPIRED
        return ExitReason.INITIAL_GRACE_EXPIRED

    def _automatic_shutdown_disabled(self) -> bool:
        return self._persistent or self._keep_running

    def _automatic_deadline_after(self, now: float) -> float | None:
        if self._automatic_shutdown_disabled():
            return None
        grace_seconds = (
            self._last_tab_grace_seconds if self._has_seen_connection else self._initial_grace_seconds
        )
        return now + grace_seconds

    def _refresh_deadline(self) -> None:
        if self._shutdown_state is ShutdownState.EXIT_REQUESTED or self._leases:
            return
        self._shutdown_deadline = self._automatic_deadline_after(self._clock())

    def _select_exit(self, reason: ExitReason) -> None:
        self._shutdown_state = ShutdownState.EXIT_REQUESTED
        self._shutdown_reason = reason
        self._shutdown_deadline = None


__all__ = (
    "ActivityToken",
    "ConnectionLease",
    "ExitReason",
    "LifecycleController",
    "LifecycleRejectedError",
    "LifecycleSnapshot",
    "QuitPreparation",
    "QuitRequestResult",
    "ShutdownState",
    "WrongInstanceError",
)
