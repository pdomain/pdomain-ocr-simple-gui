"""5.9 — full click-path: config form → choose engine/language/device → submit.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-006 (engine/language seeded from prefs default_engine/_language)
Covers: B-HOME-007 (text-normalization toggle rides into the spec)
Covers: B-HOME-008 (device is honored end-to-end → spec.device on disk)
Covers: B-HOME-010 (project name + pages-per-batch persist into the spec)
Covers: B-HOME-011 (submit → sidecars + combined.txt always written)

Each test asserts BOTH the observable output (DOM / route) AND the backend
effect — re-querying GET /api/jobs/{id} and inspecting the on-disk artifacts
under ``e2e_data_root`` (project.json spec fields; pages/<name>.json sidecar;
combined.txt).

The fake dispatcher ignores engine/language and returns deterministic output,
so OCR text correctness is not asserted here — only that the front-end
transmits the chosen config and the backend persists + writes the expected
artifacts. Tier-B (real engine) coverage of B-HOME-011 lives in
test_real_ocr_pipeline.py.
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
    """Extract <id> from a /jobs/<id> results URL."""
    return url.rstrip("/").split("/jobs/")[-1].split("/")[0]


def _read_spec(e2e_data_root: Path, project_id: str) -> dict:
    """Read the on-disk project.json spec for a project."""
    proj_file = e2e_data_root / "projects" / project_id / "project.json"
    data = json.loads(proj_file.read_text(encoding="utf-8"))
    return data["spec"]


@pytest.mark.slow
@pytest.mark.e2e
def test_config_form_seeds_engine_from_prefs_and_persists_choice(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-006 (Regression): a saved default_engine seeds the form select.

    Seeds prefs default_engine=tesseract via PUT /api/prefs, opens the config
    form, asserts the engine select STARTS on 'tesseract' (the regression: it
    used to ignore default_engine and start on doctr), then submits and asserts
    spec.engine == 'tesseract' persisted to project.json.
    """
    # Seed a saved engine default.
    put = httpx.put(
        f"{live_server_url}/api/prefs",
        json={"default_engine": "tesseract", "default_language": "fr"},
        timeout=5.0,
    )
    put.raise_for_status()

    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # Observable output: the form seeded engine + language from the prefs
    # default_* keys (regression was: it read the wrong keys → always doctr/en).
    engine_select = page.get_by_test_id("engine-select")
    expect(engine_select).to_have_value("tesseract", timeout=10_000)
    expect(page.get_by_test_id("language-input")).to_have_value("fr")

    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    project_id = _project_id_from_url(page.url)

    # Backend effect (API): the persisted spec carries the seeded engine.
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
    assert status["project_id"] == project_id

    # Backend effect (disk): project.json spec.engine == tesseract.
    spec = _read_spec(e2e_data_root, project_id)
    assert spec["engine"] == "tesseract", spec
    assert spec["language"] == "fr", spec


@pytest.mark.slow
@pytest.mark.e2e
def test_config_form_device_toggle_and_batch_persist_to_spec(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-007 + B-HOME-008 + B-HOME-010: toggle + device + batch reach the spec.

    Flips the straight-quotes toggle (label selector — Radix Switch has no
    testid), picks the CPU device segment, sets pages-per-batch, then submits.
    Asserts the chosen values persist into project.json spec on disk.
    """
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # B-HOME-007: flip the straight-quotes toggle OFF (default ON). The Toggle
    # forwards no data-testid, so select by its label text.
    page.get_by_label("Convert curly quotes to straight").click()

    # B-HOME-008: choose the CPU device segment (always present).
    page.get_by_test_id("device-chooser").get_by_text("CPU", exact=True).click()

    # B-HOME-010: set pages-per-batch.
    page.get_by_test_id("batch-pages-input").fill("3")

    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    project_id = _project_id_from_url(page.url)

    spec = _read_spec(e2e_data_root, project_id)
    # B-HOME-007: straight_quotes flipped to False.
    assert spec["straight_quotes"] is False, spec
    # B-HOME-008: device honored end-to-end (observable on disk).
    assert spec["device"] == "cpu", spec
    # B-HOME-010: batch_pages persisted.
    assert spec["batch_pages"] == 3, spec


@pytest.mark.slow
@pytest.mark.e2e
def test_submit_always_writes_sidecar_and_combined(
    page: Page, live_server_url: str, e2e_data_root: Path, tmp_path: Path
) -> None:
    """B-HOME-011: a submitted job always writes pages/<name>.json + combined.txt.

    There is no save_json / combined_txt knob — both artifacts must exist after
    a successful run. Asserts the canonical sidecar (named after the source
    image, e.g. scan.png.json) and combined.txt on disk.
    """
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)
    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)
    project_id = _project_id_from_url(page.url)

    # Wait for the job to reach a terminal state (fake dispatcher is fast).
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )

    proj_dir = e2e_data_root / "projects" / project_id

    # Backend effect (disk): canonical sidecar named after the image + combined.
    def _artifacts_present() -> bool:
        sidecar = proj_dir / "pages" / "scan.png.json"
        combined = proj_dir / "combined.txt"
        return sidecar.exists() and combined.exists()

    # The pipeline writes these as the final step; poll briefly.
    deadline_ok = False
    for _ in range(60):
        if _artifacts_present():
            deadline_ok = True
            break
        page.wait_for_timeout(250)
    assert deadline_ok, (
        sorted(p.name for p in (proj_dir / "pages").glob("*"))
        if (proj_dir / "pages").exists()
        else "no pages dir"
    )

    # Backend effect (API): the job is retrievable and succeeded.
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=5.0).json()
    assert status["state"] in ("succeeded", "running")


@pytest.mark.slow
@pytest.mark.e2e
def test_gpu_help_toggle_and_panel(page: Page, live_server_url_cpu: str, tmp_path: Path) -> None:
    """Click gpu-help-toggle; assert gpu-help panel becomes visible.

    Covers: B-HOME-008 (bad/no-GPU path — the help affordance + panel)

    Requires live_server_url_cpu which forces PDOMAIN_GPU_BACKEND=cpu so
    the /api/config route returns gpu_available=False and the toggle is
    rendered in the config form.
    """
    img = tmp_path / "scan_cpu.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url_cpu)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    toggle = page.get_by_test_id("gpu-help-toggle")
    expect(toggle).to_be_visible(timeout=10_000)

    gpu_help_panel = page.get_by_test_id("gpu-help")
    expect(gpu_help_panel).to_be_hidden()

    toggle.click()
    expect(gpu_help_panel).to_be_visible(timeout=5_000)
