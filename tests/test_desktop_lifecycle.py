"""Tests for the desktop runtime's browser and native lifecycle boundaries."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from pdomain_ocr_simple_gui.desktop_runtime import DesktopRuntime, LifecycleActivityMiddleware
from pdomain_ocr_simple_gui.instance import InstanceRecord
from pdomain_ocr_simple_gui.lifecycle import LifecycleController, WrongInstanceError
from pdomain_ocr_simple_gui.routes.lifecycle import router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


_ORIGIN = "http://127.0.0.1:8123"
_CAPABILITY = "a" * 64


@dataclass
class ExitRecorder:
    """Record graceful-exit requests without stopping the test process."""

    requests: int = 0

    def __call__(self) -> None:
        self.requests += 1


@dataclass
class RuntimeFixture:
    """Keep a runtime and its graceful-exit recorder together."""

    runtime: DesktopRuntime
    exits: ExitRecorder


@dataclass
class StoredPrefs:
    """Minimal preferences adapter surface exercised by lifecycle options."""

    apps: dict[str, dict[str, object]]
    writes: list[tuple[str, dict[str, object]]]

    def read(self) -> StoredPrefs:
        return self

    def write_app(self, app_id: str, payload: dict[str, object]) -> None:
        self.apps[app_id] = payload
        self.writes.append((app_id, payload))


@pytest.fixture
def runtime_fixture() -> RuntimeFixture:
    record = InstanceRecord(
        instance_id="1" * 32,
        pid=1,
        origin=_ORIGIN,
        capability=SecretStr(_CAPABILITY),
    )
    exits = ExitRecorder()
    controller = LifecycleController(record.instance_id, request_exit=exits)
    return RuntimeFixture(DesktopRuntime(record, controller), exits)


@pytest.fixture
def app(runtime_fixture: RuntimeFixture) -> FastAPI:
    test_app = FastAPI()
    test_app.state.desktop_runtime = runtime_fixture.runtime
    test_app.add_middleware(LifecycleActivityMiddleware)
    test_app.include_router(router)

    @test_app.post("/api/work")
    async def work() -> dict[str, str]:
        """Exercise activity wrapping around an ordinary API endpoint."""
        await asyncio.sleep(0)
        return {"status": "done"}

    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_ORIGIN) as async_client:
        yield async_client


def _native_headers(*, challenge: str = "challenge") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_CAPABILITY}",
        "X-Pdomain-Challenge": challenge,
    }


def _browser_headers() -> dict[str, str]:
    return {"Origin": _ORIGIN, "Host": "127.0.0.1:8123"}


@pytest.mark.asyncio
async def test_native_status_requires_instance_capability_and_echoes_challenge(
    client: AsyncClient,
) -> None:
    rejected = await client.get("/api/lifecycle/instance", headers={"X-Pdomain-Challenge": "x"})
    assert rejected.status_code == 401

    response = await client.get("/api/lifecycle/instance", headers=_native_headers(challenge="probe"))
    assert response.status_code == 200
    assert response.json() == {
        "app_id": "pdomain-ocr-simple-gui",
        "instance_id": "1" * 32,
        "challenge": "probe",
        "accepted": True,
        "message": "",
        "live_tabs": 0,
        "active_operations": 0,
    }


@pytest.mark.asyncio
async def test_headless_bootstrap_reports_unmanaged() -> None:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_ORIGIN) as client:
        response = await client.post("/api/lifecycle/bootstrap")

    assert response.status_code == 200
    assert response.json() == {"managed": False}


@pytest.mark.asyncio
async def test_bootstrap_rejects_cross_origin_and_sets_a_private_session_cookie(
    client: AsyncClient,
) -> None:
    cross_origin = await client.post(
        "/api/lifecycle/bootstrap",
        headers={"Origin": "http://evil.invalid", "Host": "127.0.0.1:8123"},
    )
    assert cross_origin.status_code == 403

    response = await client.post("/api/lifecycle/bootstrap", headers=_browser_headers())
    assert response.status_code == 200
    assert response.json() == {"managed": True, "instance_id": "1" * 32}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/lifecycle" in cookie
    assert _CAPABILITY not in response.text


@pytest.mark.asyncio
async def test_browser_quit_requires_private_cookie_and_exact_origin(
    client: AsyncClient,
) -> None:
    missing_cookie = await client.post("/api/lifecycle/browser-quit", headers=_browser_headers())
    assert missing_cookie.status_code == 401

    bootstrap = await client.post("/api/lifecycle/bootstrap", headers=_browser_headers())
    assert bootstrap.status_code == 200
    wrong_origin = await client.post(
        "/api/lifecycle/browser-quit",
        headers={"Origin": "http://evil.invalid", "Host": "127.0.0.1:8123"},
    )
    assert wrong_origin.status_code == 403


@pytest.mark.asyncio
async def test_browser_quit_requires_its_own_live_page_lease(
    client: AsyncClient, runtime_fixture: RuntimeFixture
) -> None:
    _ = await client.post("/api/lifecycle/bootstrap", headers=_browser_headers())
    _ = await runtime_fixture.runtime.attach_browser("1" * 32, "active-page")
    rejected = await client.post(
        "/api/lifecycle/browser-quit",
        headers=_browser_headers(),
        json={"page_id": "not-connected", "confirm_other_tabs": True},
    )
    assert rejected.status_code == 409
    assert runtime_fixture.exits.requests == 0
    accepted = await client.post(
        "/api/lifecycle/browser-quit",
        headers=_browser_headers(),
        json={"page_id": "active-page", "confirm_other_tabs": False},
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert runtime_fixture.exits.requests == 1


@pytest.mark.asyncio
async def test_browser_options_persist_and_apply_keep_running(
    client: AsyncClient,
    runtime_fixture: RuntimeFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pdomain_ocr_simple_gui.app as app_module

    prefs = StoredPrefs(
        apps={"pdomain-ocr-simple-gui": {"default_engine": "doctr"}},
        writes=[],
    )
    monkeypatch.setattr(app_module, "_prefs_adapter", prefs)
    bootstrap = await client.post("/api/lifecycle/bootstrap", headers=_browser_headers())
    assert bootstrap.status_code == 200

    response = await client.post(
        "/api/lifecycle/options",
        headers=_browser_headers(),
        json={"keep_running": True},
    )

    assert response.status_code == 200
    assert response.json() == {"keep_running": True}
    assert prefs.writes == [("pdomain-ocr-simple-gui", {"default_engine": "doctr", "keep_running": True})]
    assert runtime_fixture.runtime.controller.snapshot().keep_running is True


@pytest.mark.asyncio
async def test_native_show_waits_for_a_visible_browser_ack(runtime_fixture: RuntimeFixture) -> None:
    session = await runtime_fixture.runtime.attach_browser("1" * 32, "page-a")
    request = asyncio.create_task(runtime_fixture.runtime.request_show(timeout_seconds=0.2))
    message = await session.messages.get()

    assert message.request_id
    assert await runtime_fixture.runtime.acknowledge_show(session, message.request_id) is True
    assert await request is True


@pytest.mark.asyncio
async def test_old_instance_cannot_attach_a_browser_session(runtime_fixture: RuntimeFixture) -> None:
    with pytest.raises(WrongInstanceError, match="different server instance"):
        _ = await runtime_fixture.runtime.attach_browser("2" * 32, "page-a")


@pytest.mark.asyncio
async def test_activity_middleware_holds_exit_until_a_regular_api_request_completes(
    app: FastAPI,
    runtime_fixture: RuntimeFixture,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    @app.post("/api/held-work")
    async def held_work() -> dict[str, str]:
        started.set()
        await release.wait()
        return {"status": "done"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_ORIGIN) as client:
        work = asyncio.create_task(client.post("/api/held-work"))
        await started.wait()
        rejected = runtime_fixture.runtime.controller.request_quit(confirm_other_tabs=True)
        assert rejected.accepted is False
        assert rejected.active_activity_count == 1
        release.set()
        response = await work

    assert response.status_code == 200
    assert runtime_fixture.runtime.controller.snapshot().activity_count == 0


@pytest.mark.asyncio
async def test_session_replacement_keeps_the_newer_browser_connection(
    runtime_fixture: RuntimeFixture,
) -> None:
    original = await runtime_fixture.runtime.attach_browser("1" * 32, "page-a")
    replacement = await runtime_fixture.runtime.attach_browser("1" * 32, "page-a")

    assert await runtime_fixture.runtime.detach_browser(original) is False
    assert runtime_fixture.runtime.controller.snapshot().active_leases == (replacement.lease,)
    assert await runtime_fixture.runtime.detach_browser(replacement) is True


def test_websocket_session_uses_the_bootstrap_cookie_and_releases_its_lease(
    app: FastAPI,
    runtime_fixture: RuntimeFixture,
) -> None:
    with TestClient(app, base_url=_ORIGIN) as client:
        bootstrap = client.post("/api/lifecycle/bootstrap", headers=_browser_headers())
        assert bootstrap.status_code == 200

        with client.websocket_connect(
            "/api/lifecycle/session?instance_id=" + ("1" * 32) + "&page_id=page-a",
            headers={
                "Origin": _ORIGIN,
                "Host": "127.0.0.1:8123",
                "Cookie": "pdomain_lifecycle_session=" + runtime_fixture.runtime.session_cookie,
            },
        ):
            assert len(runtime_fixture.runtime.controller.snapshot().active_leases) == 1

    assert runtime_fixture.runtime.controller.snapshot().active_leases == ()
