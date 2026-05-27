"""Tests for /api/jobs routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.models import ProjectStatus


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Async HTTP client wired to the FastAPI app with tmp storage root."""

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_with_source(tmp_path, monkeypatch):
    """Client with a tmp storage root AND a real source directory with one image."""

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    # Create a tiny source image
    src = tmp_path / "source"
    src.mkdir()
    (src / "page0.png").touch()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, str(src)


JOB_PAYLOAD = {
    "name": "Test Job",
    "source_path": "/tmp/source",
    "output_dir": "/tmp/output",
    "engine": "doctr",
    "language": "en",
    "save_json": False,
    "combined_txt": True,
}


def _make_done_status_callback(project_id: str):
    """Return an async run_project mock that immediately marks the project done."""

    async def _mock_run_project(spec, dispatcher, status_callback) -> None:
        from pdomain_ocr_simple_gui.models import PageResult
        from pdomain_ocr_simple_gui.storage import write_project

        done_status = ProjectStatus(
            project_id=spec.project_id,
            state="succeeded",
            page_count=1,
            pages_done=1,
            pages=[PageResult(page_idx=0, page_name="page0.png", state="succeeded", text_preview="")],
        )
        write_project(spec, done_status)
        await status_callback(done_status)

    return _mock_run_project


class TestPostJob:
    async def test_creates_job(self, client: AsyncClient) -> None:
        resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "project_id" in data
        assert len(data["project_id"]) > 0

    async def test_created_job_is_retrievable(self, client: AsyncClient) -> None:
        resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = resp.json()["project_id"]
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        status = get_resp.json()
        assert status["project_id"] == project_id
        assert status["state"] in ("queued", "running", "succeeded", "failed", "cancelled")


class TestGetJob:
    async def test_404_for_missing(self, client: AsyncClient) -> None:
        resp = await client.get("/api/jobs/nonexistent-id")
        assert resp.status_code == 404

    async def test_returns_project_status(self, client: AsyncClient) -> None:
        post_resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        get_resp = await client.get(f"/api/jobs/{project_id}")
        status = get_resp.json()
        assert status["project_id"] == project_id
        assert "state" in status
        assert "page_count" in status
        assert "pages_done" in status
        assert "pages" in status
        # Issue #3: must include name and output_dir from ProjectSpec
        assert status["name"] == JOB_PAYLOAD["name"]
        assert status["output_dir"] == JOB_PAYLOAD["output_dir"]


class TestListJobs:
    async def test_empty_list(self, client: AsyncClient) -> None:
        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_lists_created_jobs(self, client: AsyncClient) -> None:
        await client.post("/api/jobs", json=JOB_PAYLOAD)
        await client.post("/api/jobs", json={**JOB_PAYLOAD, "name": "Job 2"})
        resp = await client.get("/api/jobs")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        names = {item["name"] for item in items}
        assert JOB_PAYLOAD["name"] in names, "list_jobs must enrich with name from ProjectSpec"


class TestDeleteJob:
    async def test_delete_removes_job(self, client: AsyncClient) -> None:
        post_resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        del_resp = await client.delete(f"/api/jobs/{project_id}")
        assert del_resp.status_code == 200
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 404

    async def test_delete_missing_is_204(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/jobs/does-not-exist")
        assert resp.status_code == 204


class TestPipelineIntegration:
    """Tests that verify run_project is wired into POST /api/jobs."""

    async def test_run_project_called_on_post(self, client_with_source) -> None:
        """POST /api/jobs triggers run_project with the created spec."""
        client, source_path = client_with_source
        call_log: list[str] = []

        async def _fake_run_project(spec, dispatcher, status_callback) -> None:
            call_log.append(spec.project_id)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _fake_run_project):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        assert resp.status_code == 202
        project_id = resp.json()["project_id"]
        assert project_id in call_log

    async def test_job_transitions_to_done_via_mock(self, client_with_source) -> None:
        """Job transitions queued → done when run_project completes."""
        client, source_path = client_with_source

        with patch(
            "pdomain_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "succeeded"

    async def test_dispatcher_passed_to_run_project(self, client_with_source) -> None:
        """run_project receives a LocalStageDispatcher instance."""
        from pdomain_ops.gpu import LocalStageDispatcher

        client, source_path = client_with_source
        received_dispatchers: list = []

        async def _capture(spec, dispatcher, status_callback) -> None:
            received_dispatchers.append(dispatcher)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _capture):
            await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )

        assert len(received_dispatchers) == 1
        assert isinstance(received_dispatchers[0], LocalStageDispatcher)


class TestCanonicalJobStates:
    """Verify that the API always emits pdomain-ocr-ops canonical state values.

    The canonical states are: queued | running | succeeded | failed | cancelled.
    Legacy values like 'done' or 'error' must never appear in API responses.
    """

    async def test_failed_job_returns_failed_not_error(self, client_with_source) -> None:
        """A job whose pipeline raises must return state='failed', not 'error'."""
        client, source_path = client_with_source

        async def _fail_run(spec, dispatcher, status_callback) -> None:
            from pdomain_ocr_simple_gui.models import PageResult
            from pdomain_ocr_simple_gui.storage import write_project

            failed_status = ProjectStatus(
                project_id=spec.project_id,
                state="failed",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="failed", text_preview="")],
            )
            write_project(spec, failed_status)
            await status_callback(failed_status)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _fail_run):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        assert resp.status_code == 202
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        state = get_resp.json()["state"]
        # Must be canonical 'failed' — never the legacy 'error' value
        assert state == "failed", f"Expected 'failed' but got {state!r}"
        assert state != "error", "Legacy 'error' state must not be returned by the API"

    async def test_succeeded_job_returns_succeeded_not_done(self, client_with_source) -> None:
        """A completed job must return state='succeeded', not the legacy 'done'."""
        client, source_path = client_with_source

        with patch(
            "pdomain_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        state = get_resp.json()["state"]
        # Must be canonical 'succeeded' — never the legacy 'done' value
        assert state == "succeeded", f"Expected 'succeeded' but got {state!r}"
        assert state != "done", "Legacy 'done' state must not be returned by the API"

    async def test_state_is_always_a_canonical_value(self, client: AsyncClient) -> None:
        """Every job state returned by the API must be a canonical pdomain-ocr-ops value."""
        CANONICAL_STATES = {"queued", "running", "succeeded", "failed", "cancelled"}
        LEGACY_STATES = {"done", "error", "pending", "created", "complete"}

        resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = resp.json()["project_id"]
        get_resp = await client.get(f"/api/jobs/{project_id}")
        state = get_resp.json()["state"]
        assert state in CANONICAL_STATES, f"Job state {state!r} is not a canonical pdomain-ocr-ops state"
        assert state not in LEGACY_STATES, f"Legacy state {state!r} must not be returned by the API"


class TestRerunJob:
    """Tests for POST /api/jobs/{project_id}/rerun."""

    async def test_rerun_returns_queued_state(self, client_with_source) -> None:
        """POST /api/jobs/:id/rerun resets status to queued."""
        client, source_path = client_with_source

        # Create a job first
        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Confirm it is done
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "succeeded"

        # Rerun it — pipeline is a no-op stub so state will be queued immediately
        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            rerun_resp = await client.post(f"/api/jobs/{project_id}/rerun")

        assert rerun_resp.status_code == 202
        data = rerun_resp.json()
        assert data["project_id"] == project_id
        assert data["state"] == "queued"

    async def test_rerun_resets_pages_to_queued(self, client_with_source) -> None:
        """After rerun, all pages should have state 'queued'."""
        client, source_path = client_with_source

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Check it reached done
        done_resp = await client.get(f"/api/jobs/{project_id}")
        assert done_resp.json()["state"] == "succeeded"

        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            await client.post(f"/api/jobs/{project_id}/rerun")

        status_resp = await client.get(f"/api/jobs/{project_id}")
        status = status_resp.json()
        assert status["state"] == "queued"
        for page in status["pages"]:
            assert page["state"] == "queued"

    async def test_rerun_404_for_missing(self, client: AsyncClient) -> None:
        """Reruns a non-existent project → 404."""
        resp = await client.post("/api/jobs/no-such-project/rerun")
        assert resp.status_code == 404

    async def test_rerun_triggers_pipeline(self, client_with_source) -> None:
        """POST /api/jobs/:id/rerun re-triggers run_project."""
        client, source_path = client_with_source

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        call_log: list[str] = []

        async def _capture(spec, dispatcher, cb):
            call_log.append(spec.project_id)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _capture):
            await client.post(f"/api/jobs/{project_id}/rerun")

        assert project_id in call_log


class TestUploadIdSource:
    """Tests for POST /api/jobs with upload_id + OutputConfig."""

    async def test_create_job_with_upload(self, tmp_path, monkeypatch) -> None:
        """POST /api/jobs with upload_id and output:managed returns 200 or 202."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

        # Pre-create a staging dir that UploadedFilesSource will find
        stage = tmp_path / "abc123"
        stage.mkdir()
        (stage / "p.png").write_bytes(b"\x89PNG")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc123",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
        assert resp.status_code in (200, 202)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc123",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
        assert resp.status_code in (200, 202)


class TestOutputModeRoundTrip:
    """output_mode written on create, returned on GET /api/jobs/{id}."""

    async def test_output_mode_returned_on_get(self, tmp_path, monkeypatch) -> None:
        """Creating a job with output.mode='managed' surfaces output_mode on GET."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Point jobs-meta sidecar to tmp
        meta_root = tmp_path / "jobs-meta"
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT", str(meta_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

        stage = tmp_path / "abc456"
        stage.mkdir()
        (stage / "p.png").write_bytes(b"\x89PNG")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            post_resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc456",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
            assert post_resp.status_code in (200, 202)
            project_id = post_resp.json()["project_id"]

            get_resp = await ac.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["output_mode"] == "managed"

    async def test_output_mode_absent_for_legacy_jobs(self, client: AsyncClient) -> None:
        """Legacy jobs (no output field) return output_mode=None or absent key."""
        post_resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        # output_mode either absent or None — not a hard value
        assert body.get("output_mode") is None
