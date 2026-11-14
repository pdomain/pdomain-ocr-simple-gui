"""Release acceptance: upload, real OCR, edit, rerun and export in a headless browser.

Covers: F-UPLOAD-OCR-DOWNLOAD-01 (release acceptance with the real engines on the CPU)
Covers: B-PAGEVIEW-010 (a saved edit reaches the exported ZIP)
Covers: B-PAGEVIEW-014 (a Tesseract rerun reaches the exported ZIP JSON)
Covers: B-PAGEVIEW-016 (page view download streams current page text)

``just ci-slow`` runs this test as part of the release preflight, through
``just real-ocr-acceptance``. It has no skip path: a missing browser, model
weight, or Tesseract install fails it.
"""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.slow, pytest.mark.e2e, pytest.mark.real_ocr]

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_STEM = "known_good_page"
EDIT_MARKER = "RELEASE ACCEPTANCE EDIT 7Q"
_CPU_FIRST_PASS_S = 600.0


def _words(text: str) -> set[str]:
    return {w.strip(".,;:!?\"'") for w in text.lower().split()} - {""}


def _overlap(produced: str, truth: set[str]) -> float:
    return len(truth & _words(produced)) / max(1, len(truth))


def _download_zip(page: Page, test_id: str) -> dict[str, str]:
    with page.expect_download(timeout=60_000) as info:
        page.get_by_test_id(test_id).click()
    with zipfile.ZipFile(io.BytesIO(Path(info.value.path()).read_bytes())) as zf:
        return {
            name: zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith((".txt", ".json"))
        }


def _page_json(files: Mapping[str, str]) -> dict[str, object]:
    data: object = json.loads(files[f"{PAGE_STEM}.json"])
    assert isinstance(data, dict)
    return {str(k): v for k, v in data.items()}  # pyright: ignore[reportUnknownVariableType]


def _engine_output(files: Mapping[str, str]) -> dict[str, object]:
    return {k: v for k, v in _page_json(files).items() if k != "edited_text"}


def _engine_text(files: Mapping[str, str]) -> str:
    text = _page_json(files).get("text")
    assert isinstance(text, str)
    return text


def _wait_for_job_success(page: Page, base_url: str) -> None:
    match = re.search(r"/jobs/([^/?#]+)", page.url)
    assert match is not None, f"no job id in {page.url}"
    url = f"{base_url}/api/jobs/{match.group(1)}"
    deadline = time.monotonic() + _CPU_FIRST_PASS_S
    body = ""
    while time.monotonic() < deadline:
        resp = page.request.get(url)
        body = resp.text()
        state: object = resp.json().get("state") if resp.ok else None
        if state == "succeeded":
            return
        if state in {"failed", "cancelled"}:
            break
        page.wait_for_timeout(2_000)
    raise AssertionError(f"real OCR job did not succeed; check model weights and engines. Job: {body}")


def _wait_for_text(page: Page, timeout_ms: int) -> str:
    page.wait_for_function(
        """() => {
            const el = document.querySelector('textarea[aria-label="OCR text"]');
            return el instanceof HTMLTextAreaElement && el.value.trim().length > 0;
        }""",
        timeout=timeout_ms,
    )
    return page.get_by_label("OCR text").input_value()


def test_upload_ocr_edit_rerun_export(page: Page, live_server_url_real_ocr_cpu: str) -> None:
    base_url = live_server_url_real_ocr_cpu
    truth = _words((FIXTURES / f"{PAGE_STEM}.gt.txt").read_text(encoding="utf-8"))

    page.goto(base_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(FIXTURES / f"{PAGE_STEM}.png"))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=15_000)
    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    _wait_for_job_success(page, base_url)

    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    ocr_text = _wait_for_text(page, 60_000)
    assert _overlap(ocr_text, truth) >= 0.6, f"real DocTR text does not match the page: {ocr_text!r}"

    edited = f"{ocr_text.rstrip()}\n{EDIT_MARKER}"
    textarea = page.get_by_label("OCR text")
    textarea.fill(edited)
    page.get_by_test_id("page-save-button").click()
    expect(page.get_by_text("Saved", exact=True).first).to_be_visible(timeout=15_000)

    after_edit = _download_zip(page, "download-images-text-json")
    assert after_edit[f"{PAGE_STEM}.txt"] == edited
    assert _page_json(after_edit).get("edited_text") == edited
    assert any(name != f"{PAGE_STEM}.txt" and EDIT_MARKER in body for name, body in after_edit.items()), (
        "combined text in the ZIP does not carry the saved edit"
    )
    doctr_output = _engine_output(after_edit)

    rerun = page.get_by_test_id("page-rerun-tesseract")
    expect(rerun).to_be_enabled(timeout=30_000)
    rerun.click()
    expect(page.get_by_text("Re-run complete", exact=True).first).to_be_visible(timeout=300_000)

    after_rerun = _download_zip(page, "download-images-text-json")
    tesseract_text = _engine_text(after_rerun)
    # The fixture page is clean enough that both engines can return the same
    # text, so compare the whole engine payload: word boxes and confidences differ.
    assert _engine_output(after_rerun) != doctr_output, "exported JSON still holds the pre-rerun DocTR output"
    assert _overlap(tesseract_text, truth) >= 0.6, f"real Tesseract text does not match: {tesseract_text!r}"
    assert after_rerun[f"{PAGE_STEM}.txt"] == edited, "rerun dropped the saved edit from the export"
    assert _page_json(after_rerun).get("edited_text") == edited
