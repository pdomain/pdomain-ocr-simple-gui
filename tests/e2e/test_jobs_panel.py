"""Browser verification: jobs-panel done-job static state, trash delete, and
e2etestjob filter.

Tasks covered:
  TASK 14 — done-job static state + trash delete (browser)
  TASK 15 — e2etestjob-* filter: test jobs never appear in jobs dock or recent list

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Opening the dock requires a running/queued job (so the jobs-pill-count badge
appears and the Jobs button is visible).  Tests that need the dock inject a
fake running job into the GET /api/jobs intercept alongside any real seeded
artifact under test.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_FAKE_RUNNING_JOB: dict[str, object] = {
    "project_id": "fake-running-job-task14",
    "name": "Fake Running Job",
    "state": "running",
    "progress_message": None,
    "page_count": 3,
    "pages_done": 1,
    "pages": [{"page_idx": 0, "page_name": "page-001", "state": "succeeded"}],
    "output_dir": "",
    "output_mode": None,
    "error": None,
}


def _open_jobs_dock(
    page: Page,
    live_server_url: str,
    extra_jobs: list[dict[str, object]],
) -> None:
    """Navigate to home, inject jobs into GET /api/jobs, and open the dock.

    Injects a fake running job (to show the jobs-pill-count badge) alongside
    any caller-supplied ``extra_jobs``.  Waits for the pill-count badge before
    clicking the Jobs button to open the utility dock.
    """
    all_jobs: list[dict[str, object]] = [_FAKE_RUNNING_JOB, *extra_jobs]

    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(all_jobs),
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # The jobs-pill-count badge appears when there is at least one in-flight job.
    expect(page.get_by_test_id("jobs-pill-count")).to_be_visible(timeout=10_000)

    # Click the Jobs button to open the utility dock.
    jobs_button = page.get_by_role("button", name=re.compile("Jobs"))
    jobs_button.click()

    # Wait for the jobs panel to become visible.
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)
    expect(page.get_by_test_id("jobs-panel-body")).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# TASK 14 — Done-job is STATIC in the dock (no shimmer / no in-progress bar)
# ---------------------------------------------------------------------------


def test_done_job_is_static_in_dock(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Task 14: a succeeded job row in the dock shows no shimmer and no progress bar.

    Opens the dock with the seeded succeeded job alongside a fake running job
    (needed to show the jobs-pill-count badge).  Asserts the done row has:
    - no .shimmer element (in-progress loading state)
    - no role="progressbar" (in-progress indicator)
    """
    seeded_entry: dict[str, object] = {
        "project_id": seeded_job_id,
        "name": "e2e-seeded",
        "state": "succeeded",
        "page_count": 1,
        "pages_done": 1,
        "pages": [{"page_idx": 0, "page_name": "page-001", "state": "succeeded"}],
        "output_dir": "/tmp/out",
        "output_mode": "next_to_source",
        "error": None,
        "progress_message": None,
    }

    _open_jobs_dock(page, live_server_url, extra_jobs=[seeded_entry])

    dock_panel = page.get_by_test_id("jobs-panel-body")

    # Find the succeeded (seeded) job row by its name text.
    seeded_row = dock_panel.locator("[data-testid='job-row']").filter(has_text="e2e-seeded")
    expect(seeded_row).to_be_visible(timeout=5_000)

    # Observable: no .shimmer class on the done row.
    shimmer_count = seeded_row.locator(".shimmer").count()
    assert shimmer_count == 0, f"Expected no .shimmer on the done job row, found {shimmer_count}"

    # Observable: no progressbar role in the done row.
    progress_count = seeded_row.get_by_role("progressbar").count()
    assert progress_count == 0, f"Expected no progressbar on the done job row, found {progress_count}"


# ---------------------------------------------------------------------------
# TASK 14 — Trash button deletes the row AND the backend record
# ---------------------------------------------------------------------------


def test_trash_button_deletes_row_and_backend(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Task 14: trash button (job-delete-{id}) removes the row from the dock
    AND the project from GET /api/jobs.

    Creates a dedicated delete-target job (not shared with other tests) to
    avoid xdist conflicts.  Verifies:

    1. The job-delete-{id} button is visible in the dock.
    2. After click, the dock refreshes and the row is gone.
    3. GET /api/jobs no longer lists the deleted project_id.
    """
    from tests.e2e.conftest import (
        _guard_seeded_roots,
        _write_job_meta,
        _write_output_txt,
        _write_page_sidecar,
        _write_project_json,
    )

    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

    project_id = "e2etestjob-del-" + uuid.uuid4().hex[:8]
    out_dir = str(outputs_root / project_id)
    _write_project_json(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecar(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="next_to_source")

    # Sanity: project exists on the server before the test.
    pre_resp = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=10.0)
    assert pre_resp.status_code == 200, f"Pre-delete GET failed: {pre_resp.status_code}"

    delete_target: dict[str, object] = {
        "project_id": project_id,
        "name": f"e2e-del-{project_id[:8]}",
        "state": "succeeded",
        "page_count": 1,
        "pages_done": 1,
        "pages": [{"page_idx": 0, "page_name": "page-001", "state": "succeeded"}],
        "output_dir": out_dir,
        "output_mode": "next_to_source",
        "error": None,
        "progress_message": None,
    }

    _open_jobs_dock(page, live_server_url, extra_jobs=[delete_target])

    # The trash button for this specific job.
    # pdomain-ui 0.6.0 renders data-testid="job-delete-{id}" on the trash button.
    trash_testid = f"job-delete-{project_id}"
    trash_button = page.get_by_test_id(trash_testid)
    expect(trash_button).to_be_visible(timeout=5_000)

    # Unroute the intercept so the dock fetches real data after the click.
    page.unroute("**/api/jobs")

    trash_button.click()

    # Observable: the job row disappears from the dock.
    # The React Query cache is invalidated; the dock re-fetches real data.
    expect(page.get_by_test_id(trash_testid)).to_have_count(0, timeout=10_000)

    # Backend effect: GET /api/jobs no longer contains the deleted project_id.
    jobs_resp = httpx.get(f"{live_server_url}/api/jobs", timeout=10.0)
    assert jobs_resp.status_code == 200
    all_ids = [j.get("project_id") for j in jobs_resp.json()]
    assert project_id not in all_ids, f"Deleted {project_id!r} still in GET /api/jobs: {all_ids}"


# ---------------------------------------------------------------------------
# TASK 15 — e2etestjob-* filter: test jobs never appear in jobs dock or recent list
# ---------------------------------------------------------------------------


def test_e2etestjob_never_appears_in_get_jobs(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Task 15: e2etestjob-* projects are excluded from GET /api/jobs.

    The backend's list_jobs() route calls is_test_job() and filters out all
    e2etestjob-* prefixed project ids.  Even though seeded_job_id exists on
    disk, it must NOT appear in the listing.
    """
    assert seeded_job_id.startswith("e2etestjob-"), (
        f"Expected e2etestjob-* prefix on seeded_job_id, got {seeded_job_id!r}"
    )

    jobs_resp = httpx.get(f"{live_server_url}/api/jobs", timeout=10.0)
    assert jobs_resp.status_code == 200
    all_ids = [j.get("project_id") for j in jobs_resp.json()]
    assert seeded_job_id not in all_ids, f"Test-job {seeded_job_id!r} leaked into GET /api/jobs: {all_ids}"


def test_e2etestjob_never_appears_in_recent_projects(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Task 15: e2etestjob-* projects are excluded from recent_projects prefs.

    The backend's _add_to_recent_projects() guards against test-job ids.
    The seeded job was never added to prefs; this test confirms that.
    """
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=10.0)
    assert prefs_resp.status_code == 200
    recent_ids = [p.get("project_id") for p in prefs_resp.json().get("recent_projects", [])]
    assert seeded_job_id not in recent_ids, (
        f"Test-job {seeded_job_id!r} leaked into recent_projects prefs: {recent_ids}"
    )


def test_directly_seeded_testjob_filtered_from_listing(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Task 15: e2etestjob-* project seeded directly in projects_root is filtered.

    Seeds a fresh e2etestjob-* project (simulating the 'seed directly in
    projects root' scenario from the task), then confirms it does NOT appear in
    GET /api/jobs or GET /api/prefs recent_projects.
    """
    from tests.e2e.conftest import (
        _guard_seeded_roots,
        _write_job_meta,
        _write_output_txt,
        _write_project_json,
    )

    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

    test_id = "e2etestjob-direct-" + uuid.uuid4().hex[:8]
    out_dir = str(outputs_root / test_id)
    _write_project_json(projects_root, test_id, output_dir=out_dir)
    _write_output_txt(outputs_root, test_id)
    _write_job_meta(jobs_meta_root, test_id, mode="next_to_source")

    # GET /api/jobs must exclude the directly-seeded test job.
    jobs_resp = httpx.get(f"{live_server_url}/api/jobs", timeout=10.0)
    assert jobs_resp.status_code == 200
    all_ids = [j.get("project_id") for j in jobs_resp.json()]
    assert test_id not in all_ids, f"Directly-seeded {test_id!r} leaked into GET /api/jobs: {all_ids}"

    # GET /api/prefs must exclude the directly-seeded test job from recent_projects.
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=10.0)
    assert prefs_resp.status_code == 200
    recent_ids = [p.get("project_id") for p in prefs_resp.json().get("recent_projects", [])]
    assert test_id not in recent_ids, f"Directly-seeded {test_id!r} leaked into recent_projects: {recent_ids}"
