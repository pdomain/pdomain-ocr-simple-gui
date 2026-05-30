"""5.7 — full click-path: file-picker upload → submit → results populated.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-002 (file-picker upload reveals chosen view + config form)
Covers: B-HOME-016 (duplicate basenames collapse to last-writer-wins on disk)

Uses Playwright's ``set_input_files`` on the hidden ``source-picker-file-pick``
input to simulate the file picker.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

# Minimal valid 1x1 greyscale PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.slow
@pytest.mark.e2e
def test_file_picker_upload_flow_reaches_results_with_page_rows(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-002: pick a PNG via file-input → submit → results + disk staging.

    Observable: chosen view + config form, then results page with a page-row.
    Backend effect: the upload staging dir holds the file, and the job is
    retrievable via GET /api/jobs/{id}.
    """
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    with page.expect_response(lambda r: "/api/uploads" in r.url and r.request.method == "POST") as resp_info:
        page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    upload_id = resp_info.value.json()["upload_id"]

    expect(page.get_by_test_id("source-picker-chosen")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # Backend effect (disk): the file landed in the staging dir.
    staging = e2e_data_root / "uploads" / upload_id
    assert (staging / "scan.png").is_file(), list(staging.iterdir())

    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=5_000)

    project_id = page.url.rstrip("/").split("/jobs/")[-1].split("/")[0]
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
    assert status["project_id"] == project_id


@pytest.mark.slow
@pytest.mark.e2e
def test_duplicate_basenames_collapse_to_one_on_disk(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-016: two files with the same basename collapse to one in staging.

    The upload route writes each file under its basename into one staging dir,
    so two ``scan.png`` (from different local dirs) collide last-writer-wins.
    Observable: the chosen view shows "2 files". Backend effect: the staging
    dir contains exactly ONE ``scan.png`` (the collision is documented, not a
    crash).
    """
    dir1 = tmp_path / "a"
    dir1.mkdir()
    dir2 = tmp_path / "b"
    dir2.mkdir()
    f1 = dir1 / "scan.png"
    f1.write_bytes(_PNG_1X1)
    f2 = dir2 / "scan.png"
    f2.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    with page.expect_response(lambda r: "/api/uploads" in r.url and r.request.method == "POST") as resp_info:
        page.get_by_test_id("source-picker-file-pick").set_input_files([str(f1), str(f2)])
    upload_id = resp_info.value.json()["upload_id"]

    # Observable: two files were selected.
    chosen = page.get_by_test_id("source-picker-chosen")
    expect(chosen).to_be_visible(timeout=10_000)
    expect(chosen).to_contain_text("2 files")

    # Backend effect (disk): only one scan.png survives the basename collision.
    staging = e2e_data_root / "uploads" / upload_id
    pngs = sorted(p.name for p in staging.iterdir() if p.name == "scan.png")
    assert pngs == ["scan.png"], list(staging.iterdir())
    assert len([p for p in staging.iterdir() if p.suffix == ".png"]) == 1, list(staging.iterdir())
