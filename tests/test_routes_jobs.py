"""Tests for /api/jobs routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from pd_ocr_simple_gui.app import app
from pd_ocr_simple_gui.models import ProjectStatus


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Async HTTP client wired to the FastAPI app with tmp storage root."""
    import pd_ocr_simple_gui.storage as storage_mod

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_with_source(tmp_path, monkeypatch):
    """Client with a tmp storage root AND a real source directory with one image."""
    import pd_ocr_simple_gui.storage as storage_mod

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)

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
        from pd_ocr_simple_gui.models import PageResult
        from pd_ocr_simple_gui.storage import write_project

        done_status = ProjectStatus(
            project_id=spec.project_id,
            state="done",
            page_count=1,
            pages_done=1,
            pages=[PageResult(page_idx=0, page_name="page0.png", state="done", text_preview="")],
        )
        write_project(spec, done_status)
        await status_callback(done_status)

    return _mock_run_project


class TestPostJob:
    async def test_creates_job(self, client: AsyncClient) -> None:
        resp = await client.post("/api/jobs", json=JOB_PAYLOAD)
        assert resp.status_code == 200
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
        assert status["state"] in ("queued", "running", "done", "error")


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

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _fake_run_project):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        assert resp.status_code == 200
        project_id = resp.json()["project_id"]
        assert project_id in call_log

    async def test_job_transitions_to_done_via_mock(self, client_with_source) -> None:
        """Job transitions queued → done when run_project completes."""
        client, source_path = client_with_source

        with patch(
            "pd_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "done"

    async def test_dispatcher_passed_to_run_project(self, client_with_source) -> None:
        """run_project receives a LocalStageDispatcher instance."""
        from pd_ocr_ops.gpu import LocalStageDispatcher

        client, source_path = client_with_source
        received_dispatchers: list = []

        async def _capture(spec, dispatcher, status_callback) -> None:
            received_dispatchers.append(dispatcher)

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _capture):
            await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )

        assert len(received_dispatchers) == 1
        assert isinstance(received_dispatchers[0], LocalStageDispatcher)


class TestRerunJob:
    """Tests for POST /api/jobs/{project_id}/rerun."""

    async def test_rerun_returns_queued_state(self, client_with_source) -> None:
        """POST /api/jobs/:id/rerun resets status to queued."""
        client, source_path = client_with_source

        # Create a job first
        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Confirm it is done
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "done"

        # Rerun it — pipeline is a no-op stub so state will be queued immediately
        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            rerun_resp = await client.post(f"/api/jobs/{project_id}/rerun")

        assert rerun_resp.status_code == 200
        data = rerun_resp.json()
        assert data["project_id"] == project_id
        assert data["state"] == "queued"

    async def test_rerun_resets_pages_to_queued(self, client_with_source) -> None:
        """After rerun, all pages should have state 'queued'."""
        client, source_path = client_with_source

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Check it reached done
        done_resp = await client.get(f"/api/jobs/{project_id}")
        assert done_resp.json()["state"] == "done"

        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _noop_run):
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

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        call_log: list[str] = []

        async def _capture(spec, dispatcher, cb):
            call_log.append(spec.project_id)

        with patch("pd_ocr_simple_gui.routes.jobs.run_project", _capture):
            await client.post(f"/api/jobs/{project_id}/rerun")

        assert project_id in call_log
