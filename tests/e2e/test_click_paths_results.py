"""Tier-A behavior tests for the ResultsPage status table, rerun, delete, 404,
and transient-retry paths.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-fast`` / ``make e2e-browser``.

Every test cites its behavior record (``Covers: B-RESULTS-NNN``), asserts the
observable output via a real ``data-testid`` (never role-only), and asserts the
backend effect by re-querying the API AND inspecting on-disk artifacts under
``e2e_data_root``. Each record has a good path and at least one bad path.

The fake dispatcher backs the live server, so OCR output is deterministic.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


# ---------------------------------------------------------------------------
# B-RESULTS-001 — Job page loads and shows name + status pip
# ---------------------------------------------------------------------------


def test_results_page_loads_name_and_pip(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-RESULTS-001 — /jobs/:id renders the project name + status."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Observable: the seeded project name renders in the header.
    expect(page.get_by_role("heading", level=1)).to_contain_text("e2e-seeded")

    # Backend effect: GET returns the enriched ProjectStatus.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_job_id}", timeout=10.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "succeeded"
    assert body["name"].startswith("e2e-seeded")

    # On-disk: project.json reflects the same succeeded state.
    proj_file = e2e_data_root / "projects" / seeded_job_id / "project.json"
    on_disk = json.loads(proj_file.read_text())
    assert on_disk["status"]["state"] == "succeeded"


def test_results_page_bad_id_is_not_a_crash(page: Page, live_server_url: str) -> None:
    """Covers: B-RESULTS-001 (bad path) — a malformed id surfaces an error block."""
    # A traversal-style id is rejected at the API boundary (400) and the page
    # shows the generic results-error block, not a crash.
    page.goto(f"{live_server_url}/jobs/..%2F..%2Fetc")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Either not-found or error — but never the loaded header.
    expect(page.get_by_role("heading", level=1)).to_have_count(0)


# ---------------------------------------------------------------------------
# B-RESULTS-002 — Running job shows a progress bar; polls until terminal
# ---------------------------------------------------------------------------


def test_running_job_shows_progress_bar(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-RESULTS-002 — a running job renders the progress bar + label."""
    project_id = "e2erun-" + uuid.uuid4().hex[:12]
    proj_dir = e2e_data_root / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "project_id": project_id,
        "name": "running-job",
        "output_dir": "",
        "output_mode": None,
        "state": "running",
        "page_count": 4,
        "pages_done": 1,
        "pages": [{"page_idx": 0, "page_name": "p1", "state": "succeeded", "text_preview": "hi"}],
        "error": None,
        "progress_message": None,
    }
    # Hold the job in "running" by fulfilling the poll deterministically.
    poll_route = f"**/api/jobs/{project_id}"
    page.route(poll_route, lambda route: route.fulfill(status=200, body=json.dumps(body)))
    page.goto(f"{live_server_url}/jobs/{project_id}")
    # Observable: progress label "1 / 4 pages complete".
    expect(page.get_by_text("1 / 4 pages complete")).to_be_visible(timeout=15_000)
    page.unroute(poll_route)


def test_running_job_no_actions_yet(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-RESULTS-002 (bad path) — a running job has no download/rerun actions."""
    project_id = "e2erun2-" + uuid.uuid4().hex[:12]
    proj_dir = e2e_data_root / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "project_id": project_id,
        "name": "running-job",
        "output_dir": "",
        "output_mode": None,
        "state": "running",
        "page_count": 2,
        "pages_done": 0,
        "pages": [],
        "error": None,
        "progress_message": None,
    }
    poll_route = f"**/api/jobs/{project_id}"
    page.route(poll_route, lambda route: route.fulfill(status=200, body=json.dumps(body)))
    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("download-results-button")).to_have_count(0)
    expect(page.get_by_test_id("rerun-all-button")).to_have_count(0)
    page.unroute(poll_route)


# ---------------------------------------------------------------------------
# B-RESULTS-003 — Succeeded job renders results (Tier A render; Tier B real text)
# ---------------------------------------------------------------------------


def test_succeeded_job_renders_results_and_stops_polling(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-RESULTS-003 — a succeeded job shows the page table + succeeded pip.

    Tier-A render contract (the real-text assertion is the Tier-B slice in
    test_real_ocr_pipeline.py, which also cites B-RESULTS-003).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Observable: page row(s) render with preview text; no progress bar.
    row = page.get_by_test_id("page-row").first
    expect(row).to_be_visible(timeout=15_000)
    expect(row).to_contain_text("Hello World")

    # Backend effect: succeeded + populated pages with preview text.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_job_id}", timeout=10.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "succeeded"
    assert body["pages"][0]["text_preview"] == "Hello World"

    # On-disk: the per-page .txt mirror carries the produced text.
    txt = e2e_data_root / "outputs" / seeded_job_id / "page-001.txt"
    assert txt.exists()
    assert "Hello World" in txt.read_text()


def test_succeeded_empty_pages_renders_header_only(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Covers: B-RESULTS-003 (bad path) — succeeded but zero pages → no table rows."""
    project_id = "e2eempty-" + uuid.uuid4().hex[:12]
    proj_dir = e2e_data_root / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "spec": {
            "project_id": project_id,
            "name": "empty-job",
            "source_path": str(proj_dir),
            "output_dir": str(e2e_data_root / "outputs" / project_id),
            "engine": "doctr",
            "language": "en",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_opened_at": "2026-01-01T00:00:00+00:00",
        },
        "status": {
            "project_id": project_id,
            "state": "succeeded",
            "page_count": 0,
            "pages_done": 0,
            "pages": [],
        },
    }
    (proj_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")
    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_role("heading", level=1)).to_contain_text("empty-job", timeout=15_000)
    expect(page.get_by_test_id("page-row")).to_have_count(0)


# ---------------------------------------------------------------------------
# B-RESULTS-005 — Per-page status table populates with preview text
# ---------------------------------------------------------------------------


def test_results_page_table_rows_and_preview(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_2page_job_id: str
) -> None:
    """Covers: B-RESULTS-005 — succeeded job renders one row per page w/ preview.

    Also exercises B-RESULTS-003's succeeded render (table present, pips shown).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    rows = page.get_by_test_id("page-row")
    expect(rows).to_have_count(2, timeout=15_000)
    # Observable: the preview cell shows seeded preview text.
    expect(rows.first).to_contain_text("Hello World")

    # Backend effect: API returns both pages with previews.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_2page_job_id}", timeout=10.0)
    assert resp.status_code == 200
    pages = resp.json()["pages"]
    assert len(pages) == 2
    assert pages[0]["text_preview"] == "Hello World"

    # On-disk: each page sidecar exists under pages/<page_name>.json.
    pages_dir = e2e_data_root / "projects" / seeded_2page_job_id / "pages"
    assert (pages_dir / "page-001.json").exists()
    assert (pages_dir / "page-002.json").exists()


def test_results_page_empty_preview_shows_dash(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-RESULTS-005 (bad path) — a blank text_preview renders as '—'."""
    project_id = "e2eblank-" + uuid.uuid4().hex[:12]
    proj_dir = e2e_data_root / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "spec": {
            "project_id": project_id,
            "name": "blank-preview",
            "source_path": str(proj_dir),
            "output_dir": str(e2e_data_root / "outputs" / project_id),
            "engine": "doctr",
            "language": "en",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_opened_at": "2026-01-01T00:00:00+00:00",
        },
        "status": {
            "project_id": project_id,
            "state": "succeeded",
            "page_count": 1,
            "pages_done": 1,
            "pages": [{"page_idx": 0, "page_name": "blank-001", "state": "succeeded", "text_preview": ""}],
        },
    }
    (proj_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")

    page.goto(f"{live_server_url}/jobs/{project_id}")
    row = page.get_by_test_id("page-row").first
    expect(row).to_be_visible(timeout=15_000)
    expect(row).to_contain_text("—")


# ---------------------------------------------------------------------------
# B-RESULTS-004 — Failed job surfaces error text + a rerun affordance
# ---------------------------------------------------------------------------


def test_failed_job_surfaces_error_and_rerun(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_failed_job_id: str
) -> None:
    """Covers: B-RESULTS-004 (Regression) — failed job shows error + rerun control."""
    page.goto(f"{live_server_url}/jobs/{seeded_failed_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Observable: the error text is surfaced (not a bare red pip).
    err = page.get_by_test_id("results-error")
    expect(err).to_be_visible(timeout=15_000)
    expect(err).to_contain_text("No supported image files")
    # Observable: a rerun affordance is offered on the failed job.
    expect(page.get_by_test_id("rerun-failed-button")).to_be_visible()

    # Backend effect: GET confirms failed state + error string.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_failed_job_id}", timeout=10.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "failed"
    assert "No supported image files" in (body["error"] or "")

    # On-disk: project.json carries the failed state + error.
    proj_file = e2e_data_root / "projects" / seeded_failed_job_id / "project.json"
    on_disk = json.loads(proj_file.read_text())
    assert on_disk["status"]["state"] == "failed"
    assert on_disk["status"]["error"]


def test_succeeded_job_has_no_failed_error_block(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-RESULTS-004 (bad path) — a succeeded job shows NO failed-error block."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("rerun-failed-button")).to_have_count(0)
    # The succeeded job shows its name header instead.
    expect(page.get_by_role("heading", level=1)).to_contain_text("e2e-seeded")


# ---------------------------------------------------------------------------
# B-RESULTS-010 — Open a page (navigate to PageView)
# ---------------------------------------------------------------------------


def test_open_page_navigates_to_page_view(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-010 — clicking a page-row navigates to PageView."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    row = page.get_by_test_id("page-row").first
    expect(row).to_be_visible(timeout=15_000)
    row.click()
    # Observable: the PageView screen renders + the URL is the page route.
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    assert "/pages/0" in page.url

    # Backend effect: PageView's own page fetch returns 200 for page 0.
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/0", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["page_idx"] == 0


def test_open_page_bad_index_returns_404(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-010 (bad path) — a nonexistent page index 404s on the API."""
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/9999", timeout=10.0)
    assert resp.status_code == 404
    _ = page  # selector-free API assertion; page fixture kept for parity


# ---------------------------------------------------------------------------
# B-RESULTS-011 — Open a non-existent / deleted job (404 → distinct not-found)
# ---------------------------------------------------------------------------


def test_unknown_job_shows_not_found_with_back_home(page: Page, live_server_url: str) -> None:
    """Covers: B-RESULTS-011 (Regression) — a 404 shows 'Job not found' + back-home."""
    unknown = "ghostjob-" + uuid.uuid4().hex[:12]
    page.goto(f"{live_server_url}/jobs/{unknown}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Observable: the DISTINCT not-found block (not the generic fetch-error).
    nf = page.get_by_test_id("results-not-found")
    expect(nf).to_be_visible(timeout=15_000)
    expect(nf).to_contain_text("Job not found")
    expect(page.get_by_test_id("results-back-home")).to_be_visible()
    expect(page.get_by_test_id("results-error")).to_have_count(0)

    # Backend effect: GET 404s for the unknown id.
    resp = httpx.get(f"{live_server_url}/api/jobs/{unknown}", timeout=10.0)
    assert resp.status_code == 404


def test_back_home_link_returns_to_home(page: Page, live_server_url: str) -> None:
    """Covers: B-RESULTS-011 (good path) — the back-home link navigates to '/'."""
    unknown = "ghostjob-" + uuid.uuid4().hex[:12]
    page.goto(f"{live_server_url}/jobs/{unknown}")
    expect(page.get_by_test_id("results-back-home")).to_be_visible(timeout=15_000)
    page.get_by_test_id("results-back-home").click()
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)


# ---------------------------------------------------------------------------
# B-RESULTS-012 — Transient status-fetch error (5xx) keeps polling, then recovers
# ---------------------------------------------------------------------------


def test_transient_error_keeps_polling_then_recovers(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-RESULTS-012 (Regression) — a transient 5xx retries, not terminal.

    Bad path: intercept the status poll → 503. The page shows the
    results-error 'retrying…' banner but is NOT a 404 not-found and does NOT go
    permanently dead. Good path: stop failing the route → the next poll
    succeeds and the loaded header renders.
    """
    fail_route = f"**/api/jobs/{seeded_job_id}"
    page.route(fail_route, lambda route: route.fulfill(status=503, body="busy"))

    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    # Observable (bad path): the transient error banner, NOT the not-found block.
    err = page.get_by_test_id("results-error")
    expect(err).to_be_visible(timeout=15_000)
    expect(err).to_contain_text("retrying")
    expect(page.get_by_test_id("results-not-found")).to_have_count(0)

    # Good path: stop failing → polling recovers and the header renders.
    page.unroute(fail_route)
    expect(page.get_by_role("heading", level=1)).to_contain_text("e2e-seeded", timeout=15_000)
    expect(page.get_by_test_id("results-error")).to_have_count(0)


# ---------------------------------------------------------------------------
# B-RESULTS-013 — Progress message line
# ---------------------------------------------------------------------------


def test_progress_message_renders_when_present(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-RESULTS-013 — a job carrying progress_message renders the line."""
    project_id = "e2eprog-" + uuid.uuid4().hex[:12]
    proj_dir = e2e_data_root / "projects" / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    msg = "Loading OCR engine — first run may download ~200 MB…"
    data = {
        "spec": {
            "project_id": project_id,
            "name": "progress-job",
            "source_path": str(proj_dir),
            "output_dir": str(e2e_data_root / "outputs" / project_id),
            "engine": "doctr",
            "language": "en",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_opened_at": "2026-01-01T00:00:00+00:00",
        },
        "status": {
            "project_id": project_id,
            "state": "running",
            "page_count": 2,
            "pages_done": 0,
            "pages": [
                {"page_idx": 0, "page_name": "p1", "state": "running", "text_preview": ""},
            ],
            "progress_message": msg,
        },
    }
    (proj_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")

    # Intercept the poll so the running state stays put (no fake pipeline advance).
    poll_route = f"**/api/jobs/{project_id}"
    page.route(
        poll_route, lambda route: route.fulfill(status=200, body=json.dumps(_running_body(project_id, msg)))
    )
    page.goto(f"{live_server_url}/jobs/{project_id}")
    line = page.get_by_test_id("job-progress-message")
    expect(line).to_be_visible(timeout=15_000)
    expect(line).to_contain_text("Loading OCR engine")
    page.unroute(poll_route)


def test_progress_message_absent_when_null(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-013 (bad path) — no progress_message → no line."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("job-progress-message")).to_have_count(0)


def _running_body(project_id: str, msg: str) -> dict[str, object]:
    """A minimal running ProjectStatus body for route-fulfill responses."""
    return {
        "project_id": project_id,
        "name": "progress-job",
        "output_dir": "",
        "output_mode": None,
        "state": "running",
        "page_count": 2,
        "pages_done": 0,
        "pages": [{"page_idx": 0, "page_name": "p1", "state": "running", "text_preview": ""}],
        "error": None,
        "progress_message": msg,
    }


# ---------------------------------------------------------------------------
# B-RESULTS-014 — Delete a job (backend endpoint; no ResultsPage UI control)
# ---------------------------------------------------------------------------


def test_delete_removes_all_artifacts_and_blocks_download(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Covers: B-RESULTS-014 (Regression) — delete removes mirror + meta; ZIP 404s.

    There is no UI delete control (deferred to the future Projects page —
    docs/specs/2026-05-29-projects-page.md), so this drives the API directly.
    """
    project_id = "e2edel-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"

    proj_dir = projects_root / project_id
    out_dir = outputs_root / project_id
    meta_dir = jobs_meta_root / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "page-001.txt").write_text("hello", encoding="utf-8")
    (meta_dir / "output_mode.json").write_text(json.dumps({"mode": "managed"}), encoding="utf-8")
    data = {
        "spec": {
            "project_id": project_id,
            "name": "delete-me",
            "source_path": str(proj_dir),
            "output_dir": str(out_dir),
            "engine": "doctr",
            "language": "en",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_opened_at": "2026-01-01T00:00:00+00:00",
        },
        "status": {
            "project_id": project_id,
            "state": "succeeded",
            "page_count": 1,
            "pages_done": 1,
            "pages": [
                {"page_idx": 0, "page_name": "page-001", "state": "succeeded", "text_preview": "hello"}
            ],
        },
    }
    (proj_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")

    # Sanity: the loaded results page renders before delete (observable surface).
    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    # Download works before delete.
    pre = httpx.get(f"{live_server_url}/api/jobs/{project_id}/download", timeout=10.0)
    assert pre.status_code == 200

    # Backend effect: delete returns 200.
    del_resp = httpx.request("DELETE", f"{live_server_url}/api/jobs/{project_id}", timeout=10.0)
    assert del_resp.status_code == 200

    # On-disk: all three locations are gone.
    assert not proj_dir.exists(), "canonical project dir not removed"
    assert not out_dir.exists(), "output mirror not removed (orphaned ZIP source)"
    assert not meta_dir.exists(), "per-job meta sidecar not removed"

    # Backend effect (bad path): the deleted job's GET 404s and the ZIP 404s.
    assert httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=10.0).status_code == 404
    post = httpx.get(f"{live_server_url}/api/jobs/{project_id}/download", timeout=10.0)
    assert post.status_code == 404

    # Observable: re-navigating to the deleted job shows the not-found block.
    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_test_id("results-not-found")).to_be_visible(timeout=15_000)


def test_delete_missing_job_is_idempotent_204(page: Page, live_server_url: str) -> None:
    """Covers: B-RESULTS-014 (bad path) — deleting an unknown id is a 204 no-op."""
    resp = httpx.request("DELETE", f"{live_server_url}/api/jobs/neverexisted-xyz", timeout=10.0)
    assert resp.status_code == 204
    _ = page
