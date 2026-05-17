"""Tests for /api/jobs routes."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pd_ocr_simple_gui.app import app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Async HTTP client wired to the FastAPI app with tmp storage root."""
    import pd_ocr_simple_gui.storage as storage_mod

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


JOB_PAYLOAD = {
    "name": "Test Job",
    "source_path": "/tmp/source",
    "output_dir": "/tmp/output",
    "engine": "doctr",
    "language": "en",
    "save_json": False,
    "combined_txt": True,
}


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
