"""5.6 — full click-path: drag-drop files onto the drop zone → submit → results.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-001 (drag-drop upload reveals the chosen view + config form)
Covers: B-HOME-011 (submit → job runs, sidecars + combined.txt on disk)

Drives the REAL browser via Playwright.  Files are deposited on the
``source-picker-drop`` element using a synthetic DataTransfer object
(``dispatchEvent``-based drop), matching the ondrop handler in
SourcePicker.tsx.  This exercises the drop-zone handler, NOT the file
input — see 5.7 (test_click_paths_upload_filepicker) for the file-input
path.

After the drop the upload completes automatically (server is running with
PDOMAIN_OCR_FAKE_DISPATCHER=1), the inline config form appears, and the
test submits the job then waits for the results page to reach "succeeded"
with at least one page-row visible.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

# Minimal valid 1x1 greyscale PNG (no alpha) — small enough to upload quickly.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

_PNG_B64 = base64.b64encode(_PNG_1X1).decode()


def _dispatch_drop(page: Page, selector: str, filename: str, b64_content: str) -> None:
    """Synthesise a drop event on *selector* carrying a single File object.

    Playwright does not support native drag-and-drop onto a custom drop zone
    when the target is a ``role=button`` div rather than a real ``<input type=file>``.
    We inject a ``DataTransfer`` via the browser's JS engine directly, which
    exercises the same ``onDrop`` handler in SourcePicker.tsx that a real user
    drag would reach.
    """
    page.evaluate(
        """([sel, name, b64]) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('drop target not found: ' + sel);

            // Decode base64 → Uint8Array → Blob → File
            const binary = atob(b64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const blob = new Blob([bytes], { type: 'image/png' });
            const file = new File([blob], name, { type: 'image/png' });

            const dt = new DataTransfer();
            dt.items.add(file);

            const ev = new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt });
            el.dispatchEvent(ev);
        }""",
        [f"[data-testid='{selector}']", filename, b64_content],
    )


@pytest.mark.slow
@pytest.mark.e2e
def test_drag_drop_upload_flow_reaches_results_with_page_rows(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Drag-drop a PNG onto the drop zone → submit job → results page + disk artifacts."""
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # 1. Dispatch a synthetic drop onto the drop zone (B-HOME-001).
    _dispatch_drop(page, "source-picker-drop", "scan.png", _PNG_B64)

    # 2. Observable: chosen view + inline config form appear (upload completed).
    expect(page.get_by_test_id("source-picker-chosen")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # 3. Submit the job via the run-ocr-button (B-HOME-011).
    page.get_by_test_id("run-ocr-button").click()

    # 4. Observable: redirect to the results page with at least one page-row.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=5_000)

    project_id = page.url.rstrip("/").split("/jobs/")[-1].split("/")[0]

    # 5. Backend effect (API): job retrievable.
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
    assert status["project_id"] == project_id

    # 6. Backend effect (disk): sidecar named after the dropped image +
    #    combined.txt are always written (B-HOME-011 — no save_json knob).
    proj_dir = e2e_data_root / "projects" / project_id
    sidecar = proj_dir / "pages" / "scan.png.json"
    combined = proj_dir / "combined.txt"
    found = False
    for _ in range(60):
        if sidecar.exists() and combined.exists():
            found = True
            break
        page.wait_for_timeout(250)
    assert found, (
        sorted(p.name for p in (proj_dir / "pages").glob("*"))
        if (proj_dir / "pages").exists()
        else "no pages dir"
    )
    sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "text" in sidecar_data and "words" in sidecar_data, sidecar_data.keys()
