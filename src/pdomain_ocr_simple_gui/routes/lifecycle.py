"""Native and browser lifecycle endpoints for desktop-managed servers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

import anyio
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.desktop_runtime import SESSION_COOKIE_NAME, BrowserSession, DesktopRuntime
from pdomain_ocr_simple_gui.lifecycle import LifecycleRejectedError, WrongInstanceError

if TYPE_CHECKING:
    from starlette.types import Scope

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


class _HeadlessBootstrapReply(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    managed: Literal[False] = False


class _ManagedBootstrapReply(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    managed: Literal[True] = True
    instance_id: str


class _BrowserQuitCommand(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    confirm_other_tabs: bool = False
    page_id: str | None = Field(default=None, min_length=1, max_length=128)


class _BrowserQuitReply(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    accepted: bool
    live_tabs: int = Field(ge=0)
    active_operations: int = Field(ge=0)
    message: str


class _NativeCommand(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    confirm_other_tabs: bool = False


class _LifecycleOptions(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    keep_running: bool


class _LifecycleOptionsReply(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    keep_running: bool


class _ShowAck(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    type: Literal["show_ack"]
    request_id: str = Field(min_length=1)


def _runtime_from_scope(scope: Scope) -> DesktopRuntime | None:
    app = scope.get("app")
    state = getattr(app, "state", None)
    runtime = getattr(state, "desktop_runtime", None)
    if isinstance(runtime, DesktopRuntime):
        return runtime
    return None


def _runtime_from_request(request: Request) -> DesktopRuntime | None:
    return _runtime_from_scope(request.scope)


def _runtime_from_websocket(websocket: WebSocket) -> DesktopRuntime | None:
    return _runtime_from_scope(websocket.scope)


def _managed_runtime(request: Request) -> DesktopRuntime:
    runtime = _runtime_from_request(request)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Desktop lifecycle management is unavailable")
    return runtime


def _require_browser_origin(request: Request, runtime: DesktopRuntime) -> None:
    if not runtime.same_browser_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(status_code=403, detail="Lifecycle requests must use this server's origin")


def _require_browser_session(request: Request, runtime: DesktopRuntime) -> None:
    if not runtime.same_browser_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(status_code=403, detail="Lifecycle requests must use this server's origin")
    if not runtime.valid_browser_session(
        request.headers.get("origin"), request.headers.get("host"), request.cookies.get(SESSION_COOKIE_NAME)
    ):
        raise HTTPException(status_code=401, detail="Lifecycle session is missing or invalid")


def _native_challenge(request: Request, runtime: DesktopRuntime) -> str:
    challenge = runtime.native_challenge(
        request.headers.get("authorization"), request.headers.get("x-pdomain-challenge")
    )
    if challenge is None:
        raise HTTPException(status_code=401, detail="Desktop instance capability is missing or invalid")
    return challenge


@router.post("/bootstrap", response_model=_HeadlessBootstrapReply | _ManagedBootstrapReply)
async def bootstrap_lifecycle(
    request: Request, response: Response, _: Annotated[None, Depends(require_token)]
) -> _HeadlessBootstrapReply | _ManagedBootstrapReply:
    """Issue a private browser session for a desktop-managed server."""
    runtime = _runtime_from_request(request)
    if runtime is None:
        return _HeadlessBootstrapReply()
    _require_browser_origin(request, runtime)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=runtime.session_cookie,
        httponly=True,
        samesite="strict",
        path="/api/lifecycle",
    )
    return _ManagedBootstrapReply(instance_id=runtime.record.instance_id)


@router.get("/instance")
async def instance_status(request: Request) -> Response:
    """Return an authenticated desktop discovery response."""
    runtime = _managed_runtime(request)
    challenge = _native_challenge(request, runtime)
    return JSONResponse(runtime.instance_reply(challenge, accepted=True).model_dump())


@router.post("/show")
async def show_browser(request: Request, _: _NativeCommand) -> Response:
    """Ask a visible browser page to show this desktop instance."""
    runtime = _managed_runtime(request)
    challenge = _native_challenge(request, runtime)
    accepted = await runtime.request_show()
    message = "" if accepted else "No visible browser page acknowledged the show request"
    return JSONResponse(runtime.instance_reply(challenge, accepted=accepted, message=message).model_dump())


@router.post("/quit")
async def native_quit(request: Request, command: _NativeCommand) -> Response:
    """Request a confirmed graceful exit from a native launcher."""
    runtime = _managed_runtime(request)
    challenge = _native_challenge(request, runtime)
    result = runtime.controller.request_quit(confirm_other_tabs=command.confirm_other_tabs)
    message = _quit_message(result.other_tab_count, result.active_activity_count)
    return JSONResponse(
        runtime.instance_reply(challenge, accepted=result.accepted, message=message).model_dump()
    )


@router.post("/browser-quit", response_model=_BrowserQuitReply)
async def browser_quit(request: Request, command: _BrowserQuitCommand | None = None) -> _BrowserQuitReply:
    """Request a confirmed graceful exit from a same-origin browser session."""
    runtime = _managed_runtime(request)
    _require_browser_session(request, runtime)
    if command is None or command.page_id is None:
        raise HTTPException(status_code=409, detail="Reconnect this page before quitting")
    confirm_other_tabs = command.confirm_other_tabs
    try:
        result = runtime.controller.request_quit(
            confirm_other_tabs=confirm_other_tabs, caller_page_id=command.page_id
        )
    except LifecycleRejectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    snapshot = runtime.controller.snapshot()
    return _BrowserQuitReply(
        accepted=result.accepted,
        live_tabs=len(snapshot.active_leases),
        active_operations=result.active_activity_count,
        message=_quit_message(result.other_tab_count, result.active_activity_count),
    )


@router.post("/options", response_model=_LifecycleOptionsReply)
async def update_lifecycle_options(request: Request, options: _LifecycleOptions) -> _LifecycleOptionsReply:
    """Persist and apply a browser-authenticated desktop lifecycle preference."""
    runtime = _managed_runtime(request)
    _require_browser_session(request, runtime)
    from pdomain_ocr_simple_gui.app import get_prefs_adapter
    from pdomain_ocr_simple_gui.constants import APP_ID

    prefs_adapter = get_prefs_adapter()
    if prefs_adapter is None:
        raise HTTPException(status_code=503, detail="Preferences are unavailable")
    current = prefs_adapter.read()
    payload = dict(current.apps.get(APP_ID) or {})
    payload["keep_running"] = options.keep_running
    prefs_adapter.write_app(APP_ID, payload)
    runtime.controller.set_keep_running(options.keep_running)
    return _LifecycleOptionsReply(keep_running=options.keep_running)


@router.websocket("/session")
async def lifecycle_session(websocket: WebSocket, instance_id: str, page_id: str) -> None:
    """Maintain one browser lease and relay native show requests to that page."""
    runtime = _runtime_from_websocket(websocket)
    if runtime is None:
        await websocket.close(code=1013)
        return
    if not runtime.valid_browser_session(
        websocket.headers.get("origin"),
        websocket.headers.get("host"),
        websocket.cookies.get(SESSION_COOKIE_NAME),
    ):
        await websocket.close(code=4403)
        return
    try:
        session = await runtime.attach_browser(instance_id, page_id)
    except WrongInstanceError:
        await websocket.close(code=4409)
        return
    except LifecycleRejectedError:
        await websocket.close(code=1012)
        return

    await websocket.accept()
    try:
        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(_send_show_messages, websocket, session)
            try:
                while True:
                    try:
                        acknowledgement = _ShowAck.model_validate_json(await websocket.receive_text())
                    except ValidationError:
                        continue
                    _ = await runtime.acknowledge_show(session, acknowledgement.request_id)
            except WebSocketDisconnect:
                task_group.cancel_scope.cancel()
    finally:
        _ = await runtime.detach_browser(session)


async def _send_show_messages(websocket: WebSocket, session: BrowserSession) -> None:
    while True:
        request = await session.messages.get()
        await websocket.send_json({"type": "show", "request_id": request.request_id})


def _quit_message(other_tab_count: int, active_operation_count: int) -> str:
    if active_operation_count:
        return "Active work must finish before quitting"
    if other_tab_count:
        return "Other browser tabs require confirmation before quitting"
    return ""
