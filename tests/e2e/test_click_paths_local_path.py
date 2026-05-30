"""5.8 — full click-path: local path input → output destination → submit.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-003 (local path input reveals the config form for a folder)
Covers: B-HOME-009 (output destination → output_mode.json + spec.output_dir)
Covers: B-HOME-019 (invalid output config → 400 surfaced in the form alert)

The server runs with ``PDOMAIN_OCR_FAKE_DISPATCHER=1`` so jobs complete
immediately with deterministic output.
"""

from __future__ import annotations

import json
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


def _project_id_from_url(url: str) -> str:
    return url.rstrip("/").split("/jobs/")[-1].split("/")[0]


@pytest.mark.slow
@pytest.mark.e2e
def test_local_path_folder_next_to_source_output(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-003 + B-HOME-009: folder path → next_to_source output writes in place.

    A folder source defaults the output to next_to_source, so OCR output lands
    in the source folder. Asserts the results page renders, output_mode.json
    records 'next_to_source', and spec.output_dir == the source folder.
    """
    folder = tmp_path / "scans"
    folder.mkdir()
    (folder / "page-001.png").write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # B-HOME-003: path input → config form.
    path_input = page.get_by_test_id("source-picker-path-input")
    path_input.fill(str(folder))
    path_input.press("Enter")
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # B-HOME-009: a folder defaults output to next_to_source; submit.
    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    project_id = _project_id_from_url(page.url)

    # Backend effect (API): output_mode persisted as next_to_source.
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
    assert status.get("output_mode") == "next_to_source", status

    # Backend effect (disk): output_mode.json sidecar + spec.output_dir == folder.
    meta = e2e_data_root / "jobs_meta" / project_id / "output_mode.json"
    assert json.loads(meta.read_text(encoding="utf-8"))["mode"] == "next_to_source"
    spec = json.loads((e2e_data_root / "projects" / project_id / "project.json").read_text(encoding="utf-8"))[
        "spec"
    ]
    assert spec["output_dir"] == str(folder), spec

    # next_to_source means the per-page .txt is written into the source folder.
    found = False
    for _ in range(40):
        if (folder / "page-001.txt").exists():
            found = True
            break
        page.wait_for_timeout(150)
    assert found, list(folder.iterdir())


@pytest.mark.slow
@pytest.mark.e2e
def test_invalid_output_config_is_rejected_and_shown(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    """B-HOME-019: an invalid output config → 400, surfaced in the form alert.

    Two halves:
      - Backend contract (httpx): the real resolve_output_dir rejects
        next_to_source on a non-folder (upload) source with a 400 + the exact
        OutputConfigError message.
      - Observable (browser): when the server returns 400, the config form
        renders the error in its role="alert" block and stays on HomePage.
        We force the 400 via route interception to exercise the display path
        (the UI filters out the offending option, so it can't be produced by
        clicking).
    """
    # --- Backend contract: real 400 for next_to_source on a non-folder source.
    # Stage an upload so the upload_id resolves, then request next_to_source.
    up = httpx.post(
        f"{live_server_url}/api/uploads",
        files={"files": ("scan.png", _PNG_1X1, "image/png")},
        timeout=5.0,
    )
    up.raise_for_status()
    upload_id = up.json()["upload_id"]
    bad = httpx.post(
        f"{live_server_url}/api/jobs",
        json={"upload_id": upload_id, "output": {"mode": "next_to_source"}},
        timeout=5.0,
    )
    assert bad.status_code == 400, bad.text
    assert "next_to_source requires a folder source" in bad.json()["detail"], bad.json()

    # --- Observable: a server 400 is shown in the form's role="alert".
    folder = tmp_path / "scans"
    folder.mkdir()
    (folder / "page-001.png").write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    path_input = page.get_by_test_id("source-picker-path-input")
    path_input.fill(str(folder))
    path_input.press("Enter")
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # Force the submit POST to 400 to drive the error-display path.
    page.route(
        "**/api/jobs",
        lambda route: (
            route.fulfill(status=400, body='{"detail":"output: specified output requires a path"}')
            if route.request.method == "POST"
            else route.continue_()
        ),
    )
    page.get_by_test_id("run-ocr-button").click()

    # Observable: error alert visible, still on HomePage (no navigation).
    alert = page.get_by_test_id("job-config-inline").get_by_role("alert")
    expect(alert).to_be_visible(timeout=10_000)
    expect(alert).to_contain_text("output")
    expect(page.get_by_test_id("home-page")).to_be_visible()
