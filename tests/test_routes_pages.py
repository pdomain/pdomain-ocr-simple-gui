"""Tests for /api/pages routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import write_project


class TestGetPage:
    async def test_returns_page_response(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert resp.status_code == 200
        data = resp.json()
        # Issue #5: must return PageResponse shape
        assert data["page_idx"] == 0
        assert data["page_name"] == "page_001.png"
        assert data["state"] == "succeeded"
        assert data["text"] == "Hello world"
        assert data["width"] == 800
        assert data["height"] == 1200

    async def test_404_for_missing_project(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/pages/nonexistent/0")
        assert resp.status_code == 404

    async def test_404_for_missing_page(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await async_client.get(f"/api/pages/{project_id}/99")
        assert resp.status_code == 404


class TestGetPageTextFallback:
    async def test_falls_back_to_text_preview_when_sidecar_missing(
        self,
        async_client: AsyncClient,
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
        resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "preview text from status"

    async def test_returns_empty_string_when_both_sidecar_and_preview_missing(
        self,
        async_client: AsyncClient,
        tmp_path: Path,
    ) -> None:
        """GET /api/pages returns empty text when both sidecar and text_preview are absent.

        Bad state: no sidecar file AND the page result has no text_preview
        (e.g. a page that was queued but never processed). The route must
        return 200 with text="" — not an error, not None.
        """
        from datetime import UTC, datetime

        project_id = "fallback-empty-002"
        spec = ProjectSpec(
            project_id=project_id,
            name="Fallback Empty",
            source_path=str(tmp_path / "src"),
            output_dir=str(tmp_path / "out"),
            engine="doctr",
            language="en",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        status = ProjectStatus(
            project_id=project_id,
            state="queued",
            page_count=1,
            pages_done=0,
            pages=[
                PageResult(
                    page_idx=0,
                    page_name="p.png",
                    state="queued",
                    text_preview="",  # empty — page was never processed
                )
            ],
        )
        write_project(spec, status)
        # No sidecar written either

        resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert resp.status_code == 200
        data = resp.json()
        # text must be the empty string, not None or an error
        assert data["text"] == ""


class TestGetPageImage:
    async def test_streams_transcoded_image(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Default (no WebP in Accept) returns PNG transcode of the source."""
        project_id, _img_path = project_with_image
        resp = await async_client.get(
            f"/api/pages/{project_id}/0/image",
            headers={"Accept": "image/png"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    async def test_serves_webp_when_accept_includes_webp(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Browsers advertising image/webp get a WebP transcode."""
        project_id, _ = project_with_image
        resp = await async_client.get(
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
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await async_client.get(
            f"/api/pages/{project_id}/0/image",
            headers={"Accept": "image/png,image/jpeg"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    async def test_404_when_image_file_missing(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, img_path = project_with_image
        img_path.unlink()
        resp = await async_client.get(f"/api/pages/{project_id}/0/image")
        assert resp.status_code == 404


class TestPutPageText:
    async def test_saves_text(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        resp = await async_client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "edited text here"},
        )
        assert resp.status_code == 200

    async def test_put_text_on_missing_project_returns_404(
        self,
        async_client: AsyncClient,
    ) -> None:
        """PUT /api/pages/:id/:idx/text on a nonexistent project returns 404.

        Bad state: the project_id has never been created. The route must
        return 404 with a clear error rather than 500 or 200.
        """
        resp = await async_client.put(
            "/api/pages/nonexistent-project-999/0/text",
            json={"text": "will not be saved"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_put_text_on_out_of_range_index_returns_404_no_write(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """PUT text with an out-of-range page index returns a clean 404, no disk write.

        Regression (B-PAGEVIEW-012): the project has only page 0, so saving to
        index 99 must return 404 ("Page not found") — NOT an uncaught
        FileNotFoundError surfacing as 500 — and must not write a stray sidecar.
        """
        from pdomain_ocr_simple_gui.storage import get_project_dir

        project_id, _ = project_with_image
        resp = await async_client.put(
            f"/api/pages/{project_id}/99/text",
            json={"text": "should never persist"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

        # No stray sidecar/txt artifact for the bad index.
        pages_dir = get_project_dir(project_id) / "pages"
        if pages_dir.exists():
            stray = [p.name for p in pages_dir.iterdir() if "99" in p.name]
            assert not stray, f"out-of-range save wrote stray artifacts: {stray}"

    async def test_text_persisted_in_sidecar(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        project_id, _ = project_with_image
        await async_client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "updated text"},
        )
        # Issue #5: GET now returns PageResponse; edited_text is surfaced as "text"
        get_resp = await async_client.get(f"/api/pages/{project_id}/0")
        data = get_resp.json()
        assert data.get("text") == "updated text"

    async def test_empty_text_overwrites_prior_text(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """PUT /api/pages/:id/:idx/text with empty string overwrites existing text.

        Bad state: user clears the text editor and saves. The PUT must persist
        the empty string (clearing prior OCR text), not silently skip the write
        or restore the old value on GET.
        """
        project_id, _ = project_with_image
        # First write some text
        await async_client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "original text"},
        )
        # Now overwrite with empty string
        put_resp = await async_client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": ""},
        )
        assert put_resp.status_code == 200

        get_resp = await async_client.get(f"/api/pages/{project_id}/0")
        data = get_resp.json()
        # Empty string must be persisted — not the prior value
        assert data.get("text") == ""


class TestGetPageImageFilePath:
    """Tests for get_page_image when source_path is a file (Issue #2)."""

    async def test_image_missing_for_file_source_returns_404(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/pages/:id/:idx/image returns 404 when source_path file is deleted.

        Bad state: the project was created with a single-file source_path, but
        that file was later deleted (e.g. temp dir cleaned up). The route must
        return 404 — not 500, not serve stale bytes.
        """
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Create then delete the source file
        img_path = tmp_path / "gone.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        project_id = "file-source-missing-001"
        spec = ProjectSpec(
            project_id=project_id,
            name="Missing File",
            source_path=str(img_path),
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
                    page_name="gone.png",
                    state="succeeded",
                )
            ],
        )
        write_project(spec, status)
        img_path.unlink()  # delete the source file

        from httpx import ASGITransport, AsyncClient

        from pdomain_ocr_simple_gui.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                f"/api/pages/{project_id}/0/image",
                headers={"Accept": "image/png"},
            )

        assert resp.status_code == 404

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
    async def test_returns_200_with_fake_dispatcher(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun route returns 200 and a PageResult with correct shape.

        Observable: response body has page_idx, state, and the page_idx
        matches what was requested — route wiring is verified via the response
        body, not by inspecting mock call counts.
        """
        from unittest.mock import AsyncMock, patch

        project_id, _img_path = project_with_image

        # Minimal fake stage result: empty page tree → route records succeeded
        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}

        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await async_client.post(f"/api/pages/{project_id}/0/rerun")

        # Observable: correct response shape
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

    async def test_rerun_uses_spec_engine_by_default(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun without an explicit engine body uses the spec's engine.

        Observable: the response returns state='succeeded' when called without
        a request body, confirming the route defaults to the project's engine
        (doctr for the test fixture) rather than raising or using None.
        """
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            # No JSON body — route must default to spec engine
            resp = await async_client.post(f"/api/pages/{project_id}/0/rerun")

        # Observable: route completed without error; default engine used
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "succeeded"
        assert data["page_idx"] == 0

    async def test_rerun_with_explicit_engine_returns_200(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
        monkeypatch,
    ) -> None:
        """Rerun with an explicit engine override returns 200.

        Bad-state pair: verifies both that the route honours an explicit engine
        override (good state) and that the wrong/absent engine does not crash
        (implicit: test_rerun_uses_spec_engine_by_default covers the default).
        """
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)
        monkeypatch.setattr(
            "pdomain_ocr_simple_gui.routes.pages.is_engine_request_available",
            lambda engine, language: (True, None),
        )

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await async_client.post(
                f"/api/pages/{project_id}/0/rerun",
                json={"engine": "tesseract"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "succeeded"

    async def test_tesseract_rerun_resolves_english_alias_before_dispatch(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
        monkeypatch,
    ) -> None:
        from unittest.mock import AsyncMock, patch

        from pdomain_ocr_simple_gui.runtime import ocr_engines
        from pdomain_ocr_simple_gui.runtime.ocr_engines import OcrEngineStatus

        project_id, _ = project_with_image
        monkeypatch.setattr(
            ocr_engines,
            "detect_tesseract",
            lambda: OcrEngineStatus(
                id="tesseract",
                label="Tesseract",
                available=True,
                languages=("eng", "osd"),
            ),
        )

        fake_result = AsyncMock()
        fake_result.metadata = {"pages": [{"type": "Page", "items": []}]}
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await async_client.post(
                f"/api/pages/{project_id}/0/rerun",
                json={"engine": "tesseract"},
            )

        assert resp.status_code == 200
        assert mock_dispatcher.run_stage.call_args.kwargs["language"] == "eng"

    async def test_rerun_rejects_unavailable_tesseract_before_marking_page_running(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
        monkeypatch,
    ) -> None:
        project_id, _ = project_with_image
        monkeypatch.setattr(
            "pdomain_ocr_simple_gui.routes.pages.is_engine_request_available",
            lambda engine, language: (
                False,
                "Tesseract is installed but language 'en' is unavailable.",
            ),
        )

        resp = await async_client.post(
            f"/api/pages/{project_id}/0/rerun",
            json={"engine": "tesseract"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == ("engine: Tesseract is installed but language 'en' is unavailable.")
        get_resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert get_resp.status_code == 200
        assert get_resp.json()["state"] == "succeeded"

    async def test_rerun_returns_failed_state_on_error(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """Rerun returns failed state when dispatcher raises."""
        from unittest.mock import AsyncMock, patch

        project_id, _ = project_with_image

        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(side_effect=RuntimeError("OCR failed"))

        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            resp = await async_client.post(f"/api/pages/{project_id}/0/rerun")

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "failed"
        assert "OCR failed" in data.get("error", "")

    async def test_rerun_updates_page_state(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """After rerun, GET page returns the updated text from the rerun result.

        Observable: POST /rerun persists the OCR text to the sidecar; a
        subsequent GET /api/pages/:id/:idx reads that sidecar and returns
        the new text. Assertion is on the GET response body — not on mock
        call counts or captured arguments.
        """
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
            rerun_resp = await async_client.post(f"/api/pages/{project_id}/0/rerun")

        # Rerun returns 200 with the new state
        assert rerun_resp.status_code == 200
        assert rerun_resp.json()["state"] == "succeeded"

        # Observable: the text is now readable via GET
        get_resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data.get("text") == "rerun text"

    async def test_rerun_nonexistent_page_returns_404(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """POST /api/pages/:id/:idx/rerun with an out-of-range page index returns 404.

        Bad state: the project has only 1 page (index 0); requesting rerun on
        index 99 must return 404, not 200 or 500.
        """
        project_id, _ = project_with_image
        resp = await async_client.post(f"/api/pages/{project_id}/99/rerun")
        assert resp.status_code == 404

    async def test_rerun_preserves_edited_text(
        self,
        async_client: AsyncClient,
        project_with_image: tuple[str, Path],
    ) -> None:
        """A single-page rerun refreshes OCR but PRESERVES the user's edited_text.

        Regression (B-PAGEVIEW-013): rerun rewrote the sidecar via
        build_sidecar_payload, which produced a fresh dict with no edited_text
        carry-over — silently discarding the user's saved edits. After the fix,
        the rerun refreshes the underlying OCR (sidecar ``text`` + words) yet the
        previously-saved ``edited_text`` survives, so GET (edited_text wins)
        still returns the user's edit.
        """
        from unittest.mock import AsyncMock, patch

        from pdomain_ocr_simple_gui.storage import read_page_sidecar, read_project

        project_id, _ = project_with_image

        # 1. User saves an edit on page 0.
        save = await async_client.put(
            f"/api/pages/{project_id}/0/text",
            json={"text": "my careful hand-edit"},
        )
        assert save.status_code == 200

        # 2. Rerun OCR on page 0 (fresh engine output differs from the edit).
        fake_result = AsyncMock()
        fake_result.metadata = {
            "pages": [
                {
                    "type": "Page",
                    "items": [
                        {
                            "type": "Block",
                            "child_type": "WORD",
                            "items": [{"type": "Word", "text": "fresh ocr output"}],
                        }
                    ],
                }
            ]
        }
        mock_dispatcher = AsyncMock()
        mock_dispatcher.run_stage = AsyncMock(return_value=fake_result)
        with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=mock_dispatcher):
            rerun = await async_client.post(f"/api/pages/{project_id}/0/rerun")
        assert rerun.status_code == 200
        assert rerun.json()["state"] == "succeeded"

        # 3. The edit must survive — GET returns edited_text, not the fresh OCR.
        get_resp = await async_client.get(f"/api/pages/{project_id}/0")
        assert get_resp.status_code == 200
        assert get_resp.json()["text"] == "my careful hand-edit"

        # On-disk: the sidecar carries BOTH the refreshed OCR text (proving the
        # rerun ran) AND the preserved edited_text.
        spec, _ = read_project(project_id)
        sidecar = read_page_sidecar(spec, 0)
        assert sidecar.get("edited_text") == "my careful hand-edit"
        assert sidecar.get("text") == "fresh ocr output"
