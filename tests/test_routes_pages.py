"""Tests for /api/pages routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import write_page_sidecar, write_project


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with tmp storage root."""

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
def project_with_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Create a project with one page and a real (tiny) image file."""

    root = tmp_path / "projects"
    root.mkdir(exist_ok=True)
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    # Create a minimal but valid 4x4 white PNG using Pillow so transcoding works.
    from datetime import UTC, datetime
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
    png_bytes = buf.getvalue()
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


class TestGetPageTextFallback:
    async def test_falls_back_to_text_preview_when_sidecar_missing(
        self,
        client: AsyncClient,
        tmp_path: Path,
    ) -> None:
        """GET /api/pages returns status text_preview when no sidecar file exists."""
        from datetime import UTC, datetime

        project_id = "fallback-001"
        spec = ProjectSpec(
            project_id=project_id,
            name="Fallback",
            source_path=str(tmp_path / "src"),
            output_dir=str(tmp_path / "out"),
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
            pages=[
                PageResult(
                    page_idx=0,
                    page_name="p.png",
                    state="succeeded",
                    text_preview="preview text from status",
                )
            ],
        )
        write_project(spec, status)
        # Deliberately do NOT call write_page_sidecar.
        resp = await client.get(f"/api/pages/{project_id}/0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "preview text from status"


class TestGetPageImage:
    async def test_streams_transcoded_image(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Default (no WebP in Accept) returns PNG transcode of the source."""
        project_id, _img_path = project_with_image
        resp = await client.get(
            f"/api/pages/{project_id}/0/image",
            headers={"Accept": "image/png"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    async def test_serves_webp_when_accept_includes_webp(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Browsers advertising image/webp get a WebP transcode."""
        project_id, _ = project_with_image
        resp = await client.get(
            f"/api/pages/{project_id}/0/image",
            headers={"Accept": "image/webp,image/png,image/*"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"
        # WebP magic: 'RIFF' .... 'WEBP'
        assert resp.content[:4] == b"RIFF"
        assert resp.content[8:12] == b"WEBP"

    async def test_falls_back_to_png_without_webp_in_accept(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await client.get(
            f"/api/pages/{project_id}/0/image",
            headers={"Accept": "image/png,image/jpeg"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

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


class TestGetPageImageFilePath:
    """Tests for get_page_image when source_path is a file (Issue #2)."""

    async def test_serves_image_when_source_path_is_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_page_image returns image bytes when source_path is a single file."""
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # source_path is the file itself (not the parent directory)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img_path = tmp_path / "single_page.png"
        img_path.write_bytes(png_bytes)

        project_id = "file-source-test-001"
        spec = ProjectSpec(
            project_id=project_id,
            name="File Source Test",
            source_path=str(img_path),  # points directly at the file
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
            pages=[
                PageResult(
                    page_idx=0,
                    page_name="single_page.png",
                    state="succeeded",
                )
            ],
        )
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(spec, status)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                f"/api/pages/{project_id}/0/image",
                headers={"Accept": "image/png"},
            )

        assert resp.status_code == 200
        # Transcoded to PNG for the browser; original on disk is untouched.
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")
        # Original file preserved (the source we wrote in this test).
        assert img_path.read_bytes() == png_bytes


class TestPostPageRerun:
    async def test_returns_200_with_mock_dispatcher(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun route returns 200 and updated PageResult with mocked dispatcher."""
        from unittest.mock import AsyncMock, patch

        project_id, _img_path = project_with_image

        # Mock dispatcher.run_stage — must be AsyncMock since run_stage is async
        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}

        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await client.post(f"/api/pages/{project_id}/0/rerun")

        assert resp.status_code == 200
        data = resp.json()
        assert data["page_idx"] == 0
        assert data["state"] == "succeeded"

    async def test_rerun_page_n_updates_page_n_not_page_0(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rerunning page N must update page N, NOT overwrite page 0 (Issue #1)."""
        from datetime import UTC, datetime
        from unittest.mock import patch

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "page_001.png").write_bytes(png_bytes)
        (source_dir / "page_002.png").write_bytes(png_bytes)

        project_id = "two-page-rerun-test"
        spec = ProjectSpec(
            project_id=project_id,
            name="Two Page Test",
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
            page_count=2,
            pages_done=2,
            pages=[
                PageResult(
                    page_idx=0,
                    page_name="page_001.png",
                    state="succeeded",
                    text_preview="original page 0",
                ),
                PageResult(
                    page_idx=1,
                    page_name="page_002.png",
                    state="succeeded",
                    text_preview="original page 1",
                ),
            ],
        )
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(spec, status)

        # Mock dispatcher: returns a fake result with text — AsyncMock since run_stage is async
        from unittest.mock import AsyncMock

        fake_result = AsyncMock()
        fake_result.metadata = {
            "pages": [
                {
                    "type": "Page",
                    "items": [
                        {
                            "type": "Block",
                            "child_type": "WORD",
                            "items": [{"type": "Word", "text": "rerun page1 text"}],
                        }
                    ],
                }
            ]
        }
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
                resp = await ac.post(f"/api/pages/{project_id}/1/rerun")

        assert resp.status_code == 200
        data = resp.json()
        # Must update page 1, not page 0
        assert data["page_idx"] == 1
        assert data["state"] == "succeeded"

        # Critically: page 0 must be untouched
        from pdomain_ocr_simple_gui.storage import read_project

        _, updated_status = read_project(project_id)
        page0 = next(p for p in updated_status.pages if p.page_idx == 0)
        assert page0.state == "succeeded"
        assert page0.text_preview == "original page 0"

    async def test_rerun_awaits_run_stage_non_blocking(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """dispatcher.run_stage is async and must be awaited directly (Issue #10).

        run_stage is already an async method on LocalStageDispatcher — awaiting it
        yields control to the event loop without blocking.  This test verifies the
        route calls run_stage with the correct arguments.
        """
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await client.post(f"/api/pages/{project_id}/0/rerun")

        assert resp.status_code == 200
        mock_dispatcher.run_stage.assert_awaited_once()
        call_args = mock_dispatcher.run_stage.call_args
        assert call_args.args[0] == "ocr"
        assert call_args.kwargs.get("engine") == "doctr"

    async def test_rerun_returns_failed_state_on_error(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun returns failed state when dispatcher raises."""
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(side_effect=RuntimeError("OCR failed"))

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await client.post(f"/api/pages/{project_id}/0/rerun")

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "failed"
        assert "OCR failed" in data.get("error", "")

    async def test_rerun_updates_page_state(
        self,
        client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """After rerun, GET page returns updated state."""
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        fake_result = AsyncMock()
        fake_result.metadata = {
            "pages": [
                {
                    "type": "Page",
                    "items": [
                        {
                            "type": "Block",
                            "child_type": "WORD",
                            "items": [{"type": "Word", "text": "rerun text"}],
                        }
                    ],
                }
            ]
        }
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            await client.post(f"/api/pages/{project_id}/0/rerun")

        get_resp = await client.get(f"/api/pages/{project_id}/0")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data.get("text") == "rerun text"
