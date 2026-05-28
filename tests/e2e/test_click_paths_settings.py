"""5.13 — settings/prefs: investigation result + coverage of app-shell prefs seeding.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

## Finding: no user-facing prefs form in this repo

There is NO standalone settings/prefs page in pdomain-ocr-simple-gui.
The prefs surface is entirely inside the AppShell component from
``@pdomain/pdomain-ui`` (theme/density/fontScale picker rendered inside
the AppShell header via ``uiPrefsConfig``). The app-level prefs
(default_engine, default_language, recent_projects, etc.) are not
exposed in a dedicated settings form; they are set per-job via the
inline config form on the home page.

The ``PUT /api/prefs`` endpoint is called by AppShell's ``persistCommon``
and ``persistApp`` callbacks. Those are pdomain-ui internals — we cannot
reliably locate their DOM controls by testid without adding testids to the
upstream library.

## What IS tested here

This test covers the persisted prefs round-trip that IS observable from
the outside:

1. PUT /api/prefs seeds recent_projects + default_engine.
2. GET /api/prefs returns them (verify via httpx — backend persistence).
3. On reload the home page still shows the seeded recent-project row
   (end-to-end: prefs survived a page reload).

This is the only user-visible prefs state in this SPA that can be
asserted without coupling to AppShell internals.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

import httpx
from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_prefs_persist_across_reload(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """PUT /api/prefs → GET /api/prefs round-trip; page reload retains seeded project row.

    No standalone settings page exists in this SPA — see module docstring.
    """
    project_name = f"prefs-test-{seeded_job_id[:8]}"

    # 1. Seed prefs via the API.
    prefs_payload = {
        "default_engine": "tesseract",
        "recent_projects": [
            {
                "project_id": seeded_job_id,
                "name": project_name,
                "last_opened_at": "2026-02-01T00:00:00+00:00",
                "page_count": 1,
                "engine": "tesseract",
                "status": "succeeded",
            }
        ],
    }
    put_resp = httpx.put(f"{live_server_url}/api/prefs", json=prefs_payload, timeout=5.0)
    put_resp.raise_for_status()

    # 2. GET /api/prefs — verify persistence at the API level.
    get_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    get_resp.raise_for_status()
    prefs_data = get_resp.json()
    assert prefs_data.get("default_engine") == "tesseract", f"default_engine not persisted: {prefs_data!r}"
    recent = prefs_data.get("recent_projects", [])
    assert any(p.get("project_id") == seeded_job_id for p in recent), (
        f"Seeded project not in recent_projects: {recent!r}"
    )

    # 3. Page reload: home page still shows the seeded recent-project row.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    row = page.get_by_test_id("recent-project-row").first
    expect(row).to_be_visible(timeout=10_000)
    # The row label contains the project name.
    expect(row).to_have_attribute("aria-label", f"Open project {project_name}")
