"""Click-path: clear chosen source / cancel config / empty upload.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-004 (clearing an upload deletes its staging dir on disk)
Covers: B-HOME-005 (cancel config form returns to picker-only state)
Covers: B-HOME-015 (empty upload makes no request, shows no config form)

Each test asserts the observable output (DOM) and, for B-HOME-004, the
backend effect on disk under ``e2e_data_root/uploads``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.slow
@pytest.mark.e2e
def test_clearing_upload_deletes_staging_dir(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-004 (Regression): clearing a chosen upload removes its staging dir.

    Observable: the chosen view collapses and the config form disappears.
    Backend effect: DELETE /api/uploads/{id} removes
    <UPLOAD_ROOT>/<upload_id>/ — the staging dir is gone from disk.
    """
    uploads_root = e2e_data_root / "uploads"

    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Capture the upload_id from the POST /api/uploads response.
    with page.expect_response(lambda r: "/api/uploads" in r.url and r.request.method == "POST") as resp_info:
        page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    upload_id = resp_info.value.json()["upload_id"]

    # The config form appears once the upload completes; staging dir exists.
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)
    staging = uploads_root / upload_id
    assert staging.is_dir(), f"staging dir {staging} should exist after upload"

    # Clear the chosen source and assert the DELETE fires.
    with page.expect_response(
        lambda r: f"/api/uploads/{upload_id}" in r.url and r.request.method == "DELETE"
    ):
        page.get_by_test_id("source-picker-clear").click()

    # Observable: config form gone, chosen view collapsed.
    expect(page.get_by_test_id("job-config-inline")).to_be_hidden()
    expect(page.get_by_test_id("source-picker-chosen")).to_be_hidden()

    # Backend effect (disk): the staging dir is gone.
    for _ in range(40):
        if not staging.exists():
            break
        page.wait_for_timeout(100)
    assert not staging.exists(), f"staging dir {staging} must be deleted after clear"


@pytest.mark.slow
@pytest.mark.e2e
def test_cancel_config_form_returns_to_picker(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """B-HOME-005: 'Use different files' hides the config form (picker stays).

    Observable: the job-config-inline form disappears and the source picker
    drop zone is still present. No backend call is made by cancel itself.
    """
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    page.get_by_test_id("job-config-inline-cancel").click()

    expect(page.get_by_test_id("job-config-inline")).to_be_hidden()
    expect(page.get_by_test_id("source-picker-drop")).to_be_visible()


@pytest.mark.slow
@pytest.mark.e2e
def test_empty_upload_makes_no_request_and_no_form(page: Page, live_server_url: str) -> None:
    """B-HOME-015: dropping zero files makes no upload request, shows no form.

    Observable: neither the chosen view nor the config form appears.
    Backend effect: no POST /api/uploads is issued (asserted by watching for
    the absence of an upload request during the drop).
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    upload_requests: list[str] = []
    page.on(
        "request",
        lambda req: (
            upload_requests.append(req.url) if "/api/uploads" in req.url and req.method == "POST" else None
        ),
    )

    # Dispatch a drop event carrying an empty file list.
    page.evaluate(
        """() => {
            const el = document.querySelector('[data-testid="source-picker-drop"]');
            const dt = new DataTransfer();
            const ev = new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt });
            el.dispatchEvent(ev);
        }"""
    )
    page.wait_for_timeout(500)

    # Observable: no chosen view, no config form.
    expect(page.get_by_test_id("source-picker-chosen")).to_be_hidden()
    expect(page.get_by_test_id("job-config-inline")).to_be_hidden()
    # Backend effect: no upload request fired.
    assert upload_requests == [], f"empty drop must not POST /api/uploads, got {upload_requests!r}"
