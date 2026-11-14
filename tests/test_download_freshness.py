"""Downloads must reflect saved page edits and single-page reruns, not the first OCR pass."""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from PIL import Image

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_png(path: Path) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
    _ = path.write_bytes(buf.getvalue())


async def _run_two_page_job(ac: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    src = tmp_path / "source"
    src.mkdir()
    _write_png(src / "page001.png")
    _write_png(src / "page002.png")
    resp = await ac.post(
        "/api/jobs",
        json={
            "name": "Fresh Export",
            "source_path": str(src),
            "output_dir": str(tmp_path / "output"),
            "engine": "doctr",
            "language": "en",
        },
    )
    assert resp.status_code == 202
    project_id: str = resp.json()["project_id"]
    status = await ac.get(f"/api/jobs/{project_id}")
    assert status.json()["state"] == "succeeded"
    return project_id


async def _download(ac: AsyncClient, project_id: str, include: str = "text,json") -> dict[str, str]:
    resp = await ac.get(f"/api/jobs/{project_id}/download?include={include}")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


async def _rerun_dispatcher(text: str) -> AsyncMock:
    pages = await FakeStageDispatcher(text).run_ocr_batch(SimpleNamespace(images=["one"]))
    result = SimpleNamespace(metadata={"pages": pages})
    dispatcher = AsyncMock()
    dispatcher.run_stage = AsyncMock(return_value=result)
    return dispatcher


class TestDownloadAfterEdit:
    async def test_saved_edit_appears_in_page_and_combined_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        use_fake_dispatcher: FakeStageDispatcher,
    ) -> None:
        _ = use_fake_dispatcher
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            project_id = await _run_two_page_job(ac, tmp_path, monkeypatch)
            before = await _download(ac, project_id, include="text")
            engine_text = before["page001.txt"]
            assert engine_text.strip() == "fake OCR output"
            assert before["page002.txt"] == engine_text

            save = await ac.put(f"/api/pages/{project_id}/1/text", json={"text": "corrected page two"})
            assert save.status_code == 200

            after = await _download(ac, project_id, include="text")

        assert after["page002.txt"] == "corrected page two"
        assert after["page001.txt"] == engine_text
        assert after["Fresh_Export.txt"] == f"{engine_text}\n\ncorrected page two"

    async def test_saved_edit_is_carried_in_exported_json_beside_engine_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        use_fake_dispatcher: FakeStageDispatcher,
    ) -> None:
        _ = use_fake_dispatcher
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            project_id = await _run_two_page_job(ac, tmp_path, monkeypatch)
            _ = await ac.put(f"/api/pages/{project_id}/0/text", json={"text": "edited page one"})
            after = await _download(ac, project_id)

        sidecar = json.loads(after["page001.json"])
        assert sidecar["edited_text"] == "edited page one"
        assert sidecar["text"].strip() == "fake OCR output"
        assert sidecar["words"]


class TestDownloadAfterRerun:
    async def test_rerun_output_replaces_stale_page_text_and_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        use_fake_dispatcher: FakeStageDispatcher,
    ) -> None:
        _ = use_fake_dispatcher
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            project_id = await _run_two_page_job(ac, tmp_path, monkeypatch)
            before = await _download(ac, project_id)
            dispatcher = await _rerun_dispatcher("rerun engine text")
            with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=dispatcher):
                rerun = await ac.post(f"/api/pages/{project_id}/0/rerun")
            assert rerun.json()["state"] == "succeeded"
            after = await _download(ac, project_id)

        rerun_text = after["page001.txt"]
        assert rerun_text.strip() == "rerun engine text"
        assert json.loads(after["page001.json"])["text"] == rerun_text
        assert after["Fresh_Export.txt"] == f"{rerun_text}\n\n{before['page002.txt']}"

    async def test_rerun_keeps_saved_edit_in_exported_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        use_fake_dispatcher: FakeStageDispatcher,
    ) -> None:
        _ = use_fake_dispatcher
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            project_id = await _run_two_page_job(ac, tmp_path, monkeypatch)
            _ = await ac.put(f"/api/pages/{project_id}/0/text", json={"text": "hand edit"})
            dispatcher = await _rerun_dispatcher("rerun engine text")
            with patch("pdomain_ocr_simple_gui.app.get_dispatcher", return_value=dispatcher):
                _ = await ac.post(f"/api/pages/{project_id}/0/rerun")
            after = await _download(ac, project_id)

        assert after["page001.txt"] == "hand edit"
        sidecar = json.loads(after["page001.json"])
        assert sidecar["text"].strip() == "rerun engine text"
        assert sidecar["edited_text"] == "hand edit"
