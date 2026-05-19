"""Tests for /api/pages routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from pd_ocr_simple_gui.app import app
from pd_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pd_ocr_simple_gui.storage import write_page_sidecar, write_project


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with tmp storage root."""
    import pd_ocr_simple_gui.storage as storage_mod

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def project_with_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Create a project with one page and a real (tiny) image file."""
    import pd_ocr_simple_gui.storage as storage_mod

    root = tmp_path / "projects"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)

    # Create a minimal 1x1 white PNG
    from datetime import UTC, datetime

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    img_path = source_dir / "page_001.png"
    img_path.write_bytes(png_bytes)

    project_id = "pages-test-001"
    spec = ProjectSpec(
        project_id=project_id,
        name="Pages Test",
        source_path=str(source_dir),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    status = ProjectStatus(
        project_id=project_id,
        state="succeeded",
        page_count=1,
        pages_done=1,
        pages=[PageResult(page_idx=0, page_name="page_001.png", state="succeeded", text_preview="Hello")],
    )
    write_project(spec, status)
    write_page_sidecar(spec, 0, {"page_idx": 0, "text": "Hello world", "edited_text": None})
    return project_id, img_path


class TestGetPage:
    async def test_returns_page_response(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await client.get(f"/api/pages/{project_id}/0")
        assert resp.status_code == 200
        data = resp.json()
        # Issue #5: must return PageResponse shape
        assert data["page_idx"] == 0
        assert data["page_name"] == "page_001.png"
        assert data["state"] == "succeeded"
        assert data["text"] == "Hello world"
        assert data["width"] == 800
        assert data["height"] == 1200

    async def test_404_for_missing_project(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/nonexistent/0")
        assert resp.status_code == 404

    async def test_404_for_missing_page(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await client.get(f"/api/pages/{project_id}/99")
        assert resp.status_code == 404


class TestGetPageImage:
    async def test_streams_image_bytes(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, img_path = project_with_image
        resp = await client.get(f"/api/pages/{project_id}/0/image")
        assert resp.status_code == 200
        assert len(resp.content) > 0
        # Should be the same bytes as the source image
        assert resp.content == img_path.read_bytes()

    async def test_404_when_image_file_missing(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, img_path = project_with_image
        img_path.unlink()
        resp = await client.get(f"/api/pages/{project_id}/0/image")
        assert resp.status_code == 404


class TestPutPageText:
    async def test_saves_text(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "edited text here"},
        )
        assert resp.status_code == 200

    async def test_text_persisted_in_sidecar(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        await client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "updated text"},
        )
        # Issue #5: GET now returns PageResponse; edited_text is surfaced as "text"
        get_resp = await client.get(f"/api/pages/{project_id}/0")
        data = get_resp.json()
        assert data.get("text") == "updated text"


class TestPostPageRerun:
    async def test_returns_200_with_mock_pipeline(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun route returns 200 and updated PageResult when pipeline is wired."""
        from unittest.mock import patch

        project_id, _ = project_with_image

        async def _fake_run_project(spec, dispatcher, status_callback) -> None:
            from pd_ocr_simple_gui.models import PageResult, ProjectStatus
            from pd_ocr_simple_gui.storage import write_project

            done_status = ProjectStatus(
                project_id=spec.project_id,
                state="succeeded",
                page_count=1,
                pages_done=1,
                pages=[
                    PageResult(
                        page_idx=0,
                        page_name="page_001.png",
                        state="succeeded",
                        text_preview="rerun result",
                    )
                ],
            )
            write_project(spec, done_status)
            await status_callback(done_status)

        with patch("pd_ocr_simple_gui.routes.pages.run_project", _fake_run_project):
            resp = await client.post(f"/api/pages/{project_id}/0/rerun")

        assert resp.status_code == 200
        data = resp.json()
        assert data["page_idx"] == 0
        assert data["state"] == "succeeded"

    async def test_rerun_updates_page_state(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """After rerun, GET page returns updated state."""
        from unittest.mock import patch

        project_id, _ = project_with_image

        async def _fake_run_project(spec, dispatcher, status_callback) -> None:
            from pd_ocr_simple_gui.models import PageResult, ProjectStatus
            from pd_ocr_simple_gui.storage import write_project, write_txt

            updated = ProjectStatus(
                project_id=spec.project_id,
                state="succeeded",
                page_count=1,
                pages_done=1,
                pages=[
                    PageResult(
                        page_idx=0,
                        page_name="page_001.png",
                        state="succeeded",
                        text_preview="rerun text",
                    )
                ],
            )
            write_project(spec, updated)
            # Also write page sidecar so GET returns text
            from pd_ocr_simple_gui.storage import write_page_sidecar

            write_page_sidecar(spec, 0, {"page_idx": 0, "text": "rerun text"})
            write_txt(spec, 0, "rerun text")
            await status_callback(updated)

        with patch("pd_ocr_simple_gui.routes.pages.run_project", _fake_run_project):
            await client.post(f"/api/pages/{project_id}/0/rerun")

        get_resp = await client.get(f"/api/pages/{project_id}/0")
        assert get_resp.status_code == 200
        sidecar = get_resp.json()
        assert sidecar.get("text") == "rerun text"
