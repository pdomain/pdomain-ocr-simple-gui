"""Click-path: job failure / edge-case paths from the home screen.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-017 (unsupported file types → job failed with a clear error)
Covers: B-HOME-018 (oversize upload → 413 → SourcePicker error alert)
Covers: B-HOME-020 (concurrent jobs from the same screen are independent)

Each test asserts the observable output (DOM / route) and the backend effect
(GET /api/jobs re-query + on-disk project.json under ``e2e_data_root``).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _project_id_from_url(url: str) -> str:
    return url.rstrip("/").split("/jobs/")[-1].split("/")[0]


def _read_status(e2e_data_root: Path, project_id: str) -> dict:
    proj_file = e2e_data_root / "projects" / project_id / "project.json"
    return json.loads(proj_file.read_text(encoding="utf-8"))["status"]


@pytest.mark.slow
@pytest.mark.e2e
def test_unsupported_file_types_mark_job_failed(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-017: a source with no supported images → job failed, clear error.

    Uses the local path input (non-containerized local mode) pointing at a dir
    that contains only unsupported files. Asserts the results page renders and
    the job transitions to failed with a 'supported types' error.
    """
    folder = tmp_path / "no-images"
    folder.mkdir()
    (folder / "readme.txt").write_text("nothing to see")
    (folder / "noise.bmp").write_bytes(b"BM")

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    path_input = page.get_by_test_id("source-picker-path-input")
    path_input.fill(str(folder))
    path_input.press("Enter")
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)
    page.get_by_test_id("run-ocr-button").click()

    # Observable: navigated to the results page for this job.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    project_id = _project_id_from_url(page.url)

    # Backend effect (API): job ends failed with a supported-types error.
    def _failed() -> dict | None:
        body = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
        return body if body.get("state") == "failed" else None

    status = None
    for _ in range(40):
        status = _failed()
        if status is not None:
            break
        page.wait_for_timeout(150)
    assert status is not None, "job did not reach failed state"
    assert status["page_count"] == 0
    assert "supported" in (status.get("error") or "").lower(), status

    # Backend effect (disk): project.json status mirrors failed.
    disk = _read_status(e2e_data_root, project_id)
    assert disk["state"] == "failed", disk


@pytest.mark.slow
@pytest.mark.e2e
def test_oversize_upload_shows_error_alert(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """B-HOME-018: an upload rejected with 413 surfaces the SourcePicker alert.

    The live server's byte cap is large, so the 413 is driven by intercepting
    /api/uploads → 413 (faking the dependency). The pure backend 413 contract
    is also covered by tests/test_uploads.py::test_size_cap. Observable here:
    the source-picker-upload-error alert appears and no source is committed
    (no upload_id was set). Since commit 3ef73f1 ("keep OCR options visible
    before source") the config form is always rendered, so the observable for
    "no source committed" is the absence of the committed-source affordances
    (the "Use different files" cancel button), with Run OCR disabled.
    """
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    page.route(
        "**/api/uploads",
        lambda route: route.fulfill(status=413, body='{"detail":"upload exceeds size cap"}'),
    )

    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))

    # Observable (bad path): upload error alert; no source committed (form stays
    # in its no-source state — cancel affordance absent, Run OCR disabled).
    expect(page.get_by_test_id("source-picker-upload-error")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("job-config-inline-cancel")).to_be_hidden()
    expect(page.get_by_test_id("run-ocr-button")).to_be_disabled()


@pytest.mark.slow
@pytest.mark.e2e
def test_concurrent_jobs_are_independent(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-020: two jobs submitted from the same screen are independent.

    Submits two jobs from two separate source folders (navigating back to the
    home page between them). Asserts two distinct project_ids, both listed by
    GET /api/jobs, with disjoint on-disk project dirs.
    """
    folder_a = tmp_path / "book-a"
    folder_a.mkdir()
    (folder_a / "page-001.png").write_bytes(_PNG_1X1)
    folder_b = tmp_path / "book-b"
    folder_b.mkdir()
    (folder_b / "page-001.png").write_bytes(_PNG_1X1)

    def _submit(folder: Path) -> str:
        page.goto(live_server_url)
        expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
        path_input = page.get_by_test_id("source-picker-path-input")
        path_input.fill(str(folder))
        path_input.press("Enter")
        expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)
        page.get_by_test_id("run-ocr-button").click()
        expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
        return _project_id_from_url(page.url)

    id_a = _submit(folder_a)
    id_b = _submit(folder_b)

    # Observable: two distinct results routes / project ids.
    assert id_a != id_b, (id_a, id_b)

    # Backend effect (API): both jobs are listed.
    listed = {j["project_id"] for j in httpx.get(f"{live_server_url}/api/jobs", timeout=5.0).json()}
    assert {id_a, id_b}.issubset(listed), listed

    # Backend effect (disk): disjoint project dirs.
    dir_a = e2e_data_root / "projects" / id_a
    dir_b = e2e_data_root / "projects" / id_b
    assert dir_a.is_dir() and dir_b.is_dir()
    assert dir_a != dir_b
