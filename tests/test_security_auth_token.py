"""Security tests — PDOMAIN_API_TOKEN capability token and concurrent-job cap.

GH issues #18, #19, #23.

Token behaviour:
  - When PDOMAIN_API_TOKEN env var is set and non-empty, all mutating endpoints
    (POST, PUT, DELETE) plus the prefs GET and jobs list GET require either:
      Authorization: Bearer <token>
      X-API-Token: <token>
    Missing or wrong token → HTTP 401.
  - When PDOMAIN_API_TOKEN is absent or empty, all endpoints work with no auth
    (preserves local-dev usability).
  - Suite routes /api/suite/* are protected by HTTP middleware (not FastAPI Depends).

Semaphore behaviour:
  - PDOMAIN_MAX_CONCURRENT_JOBS (default 3) caps concurrent create_job calls.
  - When the semaphore is exhausted → HTTP 429.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

pytestmark = pytest.mark.anyio

_TOKEN = "test-secret-token"

_PREFS_PAYLOAD: dict[str, Any] = {
    "default_engine": "doctr",
    "default_language": "en",
    "default_output_dir": "",
    "recent_projects": [],
}

_JOB_PAYLOAD: dict[str, Any] = {
    "name": "Auth Test Job",
    "source_path": "/tmp/source",
    "output_dir": "/tmp/output",
    "engine": "doctr",
    "language": "en",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_prefs_adapter(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a mock prefs adapter so prefs routes don't need a real fs."""
    from pdomain_ops.suite.types import UIPrefs

    import pdomain_ocr_simple_gui.app as app_mod

    mock = MagicMock()
    mock.read.return_value = UIPrefs()
    mock.write_app.return_value = None
    monkeypatch.setattr(app_mod, "_prefs_adapter", mock)
    return mock


@pytest.fixture
async def secured_app_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_prefs_adapter: MagicMock,
) -> AsyncClient:
    """Async client against an app that has PDOMAIN_API_TOKEN set."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    monkeypatch.setenv("PDOMAIN_API_TOKEN", _TOKEN)
    from pdomain_ocr_simple_gui.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
async def open_app_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_prefs_adapter: MagicMock,
) -> AsyncClient:
    """Async client against an app that has NO PDOMAIN_API_TOKEN (local-dev mode)."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    from pdomain_ocr_simple_gui.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Token authentication tests — POST /api/jobs (create_job)
# ---------------------------------------------------------------------------


class TestCreateJobAuth:
    async def test_create_job_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/jobs with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.post("/api/jobs", json=_JOB_PAYLOAD)
        assert resp.status_code == 401

    async def test_create_job_rejected_with_wrong_bearer_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/jobs with wrong Bearer token → 401."""
        resp = await secured_app_client.post(
            "/api/jobs",
            json=_JOB_PAYLOAD,
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    async def test_create_job_rejected_with_wrong_x_api_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/jobs with wrong X-API-Token header → 401."""
        resp = await secured_app_client.post(
            "/api/jobs",
            json=_JOB_PAYLOAD,
            headers={"X-API-Token": "wrong-token"},
        )
        assert resp.status_code == 401

    async def test_create_job_accepted_with_bearer_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/jobs with correct Bearer token → 202."""
        resp = await secured_app_client.post(
            "/api/jobs",
            json=_JOB_PAYLOAD,
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        # 202 Accepted (or 422 from validation — but not 401)
        assert resp.status_code != 401

    async def test_create_job_accepted_with_x_api_token_header(self, secured_app_client: AsyncClient) -> None:
        """POST /api/jobs with correct X-API-Token header → not 401."""
        resp = await secured_app_client.post(
            "/api/jobs",
            json=_JOB_PAYLOAD,
            headers={"X-API-Token": _TOKEN},
        )
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Token authentication tests — GET/PUT /api/prefs
# ---------------------------------------------------------------------------


class TestPrefsAuth:
    async def test_prefs_get_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/prefs with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.get("/api/prefs")
        assert resp.status_code == 401

    async def test_prefs_put_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """PUT /api/prefs with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.put("/api/prefs", json=_PREFS_PAYLOAD)
        assert resp.status_code == 401

    async def test_prefs_get_accepted_with_bearer_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/prefs with correct Bearer token → 200."""
        resp = await secured_app_client.get(
            "/api/prefs",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        assert resp.status_code == 200

    async def test_prefs_put_accepted_with_bearer_token(self, secured_app_client: AsyncClient) -> None:
        """PUT /api/prefs with correct Bearer token → 200."""
        resp = await secured_app_client.put(
            "/api/prefs",
            json=_PREFS_PAYLOAD,
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        assert resp.status_code == 200

    async def test_prefs_get_accepted_with_x_api_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/prefs with correct X-API-Token header → 200."""
        resp = await secured_app_client.get(
            "/api/prefs",
            headers={"X-API-Token": _TOKEN},
        )
        assert resp.status_code == 200

    async def test_prefs_put_accepted_with_x_api_token(self, secured_app_client: AsyncClient) -> None:
        """PUT /api/prefs with correct X-API-Token header → 200."""
        resp = await secured_app_client.put(
            "/api/prefs",
            json=_PREFS_PAYLOAD,
            headers={"X-API-Token": _TOKEN},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Token authentication tests — GET /api/jobs (list_jobs)
# ---------------------------------------------------------------------------


class TestListJobsAuth:
    async def test_list_jobs_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/jobs with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.get("/api/jobs")
        assert resp.status_code == 401

    async def test_list_jobs_accepted_with_bearer_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/jobs with correct Bearer token → 200."""
        resp = await secured_app_client.get(
            "/api/jobs",
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Token authentication tests — POST/DELETE /api/uploads
# ---------------------------------------------------------------------------


class TestUploadsAuth:
    async def test_post_uploads_requires_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/uploads with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.post(
            "/api/uploads",
            files={"files": ("a.png", b"fake-bytes", "image/png")},
        )
        assert resp.status_code == 401

    async def test_delete_uploads_requires_token(self, secured_app_client: AsyncClient) -> None:
        """DELETE /api/uploads/{id} with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.delete("/api/uploads/deadbeef")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token authentication tests — GET /api/jobs/{project_id}
# ---------------------------------------------------------------------------


class TestGetJobByIdAuth:
    async def test_get_job_by_id_requires_token(self, secured_app_client: AsyncClient) -> None:
        """GET /api/jobs/{id} with no auth header → 401 when token env var is set."""
        resp = await secured_app_client.get("/api/jobs/0123456789abcdef")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Suite middleware tests — /api/suite/launch and /api/suite/stop
# ---------------------------------------------------------------------------


class TestSuiteAuth:
    async def test_suite_launch_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/suite/launch with no auth header → 401 via middleware."""
        resp = await secured_app_client.post("/api/suite/launch", json={})
        assert resp.status_code == 401

    async def test_suite_stop_rejected_without_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/suite/stop with no auth header → 401 via middleware."""
        resp = await secured_app_client.post("/api/suite/stop", json={})
        assert resp.status_code == 401

    async def test_suite_launch_rejected_with_wrong_token(self, secured_app_client: AsyncClient) -> None:
        """POST /api/suite/launch with wrong token → 401 via middleware."""
        resp = await secured_app_client.post(
            "/api/suite/launch",
            json={},
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("PUT", "/api/suite/device"),
            ("PUT", "/api/suite/prefs/common"),
            ("PUT", "/api/suite/prefs/apps/some-app"),
            ("POST", "/api/suite/update"),
            ("POST", "/api/suite/launch"),  # already protected — regression guard
        ],
    )
    async def test_mutating_suite_routes_require_token(
        self, secured_app_client: AsyncClient, method: str, path: str
    ) -> None:
        """Every mutating /api/suite/* path requires the token, not just launch."""
        resp = await secured_app_client.request(method, path, json={})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# No-token env-var mode — all endpoints accessible
# ---------------------------------------------------------------------------


class TestNoTokenMode:
    async def test_no_token_env_allows_prefs_get(self, open_app_client: AsyncClient) -> None:
        """GET /api/prefs with no token env var → 200 (no auth required)."""
        resp = await open_app_client.get("/api/prefs")
        assert resp.status_code == 200

    async def test_no_token_env_allows_prefs_put(self, open_app_client: AsyncClient) -> None:
        """PUT /api/prefs with no token env var → 200 (no auth required)."""
        resp = await open_app_client.put("/api/prefs", json=_PREFS_PAYLOAD)
        assert resp.status_code == 200

    async def test_no_token_env_allows_jobs_list(self, open_app_client: AsyncClient) -> None:
        """GET /api/jobs with no token env var → 200 (no auth required)."""
        resp = await open_app_client.get("/api/jobs")
        assert resp.status_code == 200

    async def test_no_token_env_allows_job_create(self, open_app_client: AsyncClient) -> None:
        """POST /api/jobs with no token env var → 202 (no auth required)."""
        resp = await open_app_client.post("/api/jobs", json=_JOB_PAYLOAD)
        # 202 or 422 (validation), but NOT 401
        assert resp.status_code != 401

    async def test_empty_token_env_allows_requests(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_prefs_adapter: MagicMock
    ) -> None:
        """PDOMAIN_API_TOKEN='' (empty string) is treated as absent → no auth."""
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.setenv("PDOMAIN_API_TOKEN", "")
        from pdomain_ocr_simple_gui.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/prefs")
        assert resp.status_code == 200


async def _create_succeeded_project(client: AsyncClient, tmp_path: Path) -> str:
    """Create a job that runs to completion via the fake dispatcher; return its id.

    Requires the ``use_fake_dispatcher`` fixture to already be active so the
    background pipeline run uses fake OCR instead of loading model weights.
    """
    from io import BytesIO

    from PIL import Image

    src = tmp_path / "rerun-source"
    src.mkdir()
    buf = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
    (src / "page001.png").write_bytes(buf.getvalue())

    resp = await client.post(
        "/api/jobs",
        json={
            "name": "rerun-cap-test",
            "source_path": str(src),
            "output_dir": str(tmp_path / "rerun-output"),
            "engine": "doctr",
            "language": "en",
        },
    )
    assert resp.status_code == 202
    project_id = resp.json()["project_id"]

    status_resp = await client.get(f"/api/jobs/{project_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["state"] == "succeeded"
    return project_id


# ---------------------------------------------------------------------------
# Concurrent jobs semaphore — 429 when exhausted
# ---------------------------------------------------------------------------


class TestMaxConcurrentJobs:
    async def test_max_concurrent_jobs_returns_429(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_prefs_adapter: MagicMock,
    ) -> None:
        """When the semaphore is exhausted, POST /api/jobs returns 429.

        Strategy: monkeypatch PDOMAIN_MAX_CONCURRENT_JOBS=1 and replace the
        semaphore with one that is already acquired, so the next POST
        immediately sees it as exhausted.
        """
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
        monkeypatch.setenv("PDOMAIN_MAX_CONCURRENT_JOBS", "1")

        import pdomain_ocr_simple_gui.routes.jobs as jobs_mod

        # Patch the semaphore with one that's already fully acquired
        sem = asyncio.Semaphore(0)  # value=0 → can't acquire at all
        monkeypatch.setattr(jobs_mod, "_job_semaphore", sem)

        from pdomain_ocr_simple_gui.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/jobs", json=_JOB_PAYLOAD)

        assert resp.status_code == 429

    async def test_rerun_respects_concurrency_cap(
        self,
        open_app_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        use_fake_dispatcher: FakeStageDispatcher,
    ) -> None:
        """Rerun is blocked by the same concurrency cap as create_job (429).

        Strategy: run a job to completion via the fake dispatcher, then
        exhaust the semaphore and confirm POST .../rerun also sees the cap
        instead of bypassing it.
        """
        project_id = await _create_succeeded_project(open_app_client, tmp_path)

        import pdomain_ocr_simple_gui.routes.jobs as jobs_mod

        monkeypatch.setattr(jobs_mod, "_job_semaphore", asyncio.Semaphore(0))

        resp = await open_app_client.post(f"/api/jobs/{project_id}/rerun")
        assert resp.status_code == 429
