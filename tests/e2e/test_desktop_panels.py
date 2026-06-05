"""Milestone H — browser verification for Compute + Updates dock panels.

Covers:
  H1: home-page testid present; compute + updates panels carry stable testids
  H2: app loads without broken-resource console errors; compute/updates panels
      open via settings dock; React Router sub-path renders a page component

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-fast`` / ``make e2e-browser``.

## Interaction contract (confirmed from pdomain-ui 0.7.0 source + testids)

Opening the settings dock:
  ``settings-slot-trigger`` → click → ``slide-over-panel`` visible

Selecting the Compute tab:
  ``settings-modal-tab-compute`` → click → ``settings-modal-panel-compute`` visible
  → ``compute-target-panel`` visible (requires intercepted /api/suite/device
    returning mode="local" + available=[{id:"cpu",...}])

Selecting the Updates tab:
  ``settings-modal-tab-updates`` → click → ``settings-modal-panel-updates`` visible
  → ``update-panel`` visible (always renders regardless of update_available)

ComputeTargetPanel gating:
  The component returns null when info.mode !== "local".
  We intercept /api/suite/device in each relevant test to return a
  synthetic local-mode payload so the panel renders without real GPU probing.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]

# ---------------------------------------------------------------------------
# Synthetic payloads
# ---------------------------------------------------------------------------

_DEVICE_LOCAL_CPU_ONLY: dict[str, object] = {
    "mode": "local",
    "available": [{"id": "cpu", "label": "CPU", "vram_total_mb": None, "vram_free_mb": None}],
    "current": "cpu",
    "effective_source": "auto",
    "offload_target": None,
}

_UPDATE_NO_UPDATE: dict[str, object] = {
    "current": "0.0.1",
    "latest": "0.0.1",
    "update_available": False,
    "changelog_url": None,
    "channel": "stable",
}

_UPDATE_AVAILABLE: dict[str, object] = {
    "current": "0.9.0",
    "latest": "0.10.0",
    "update_available": True,
    "changelog_url": "#",
    "channel": "stable",
}


# ---------------------------------------------------------------------------
# H1 / H2 — app loads without broken-resource console errors
# ---------------------------------------------------------------------------


def test_app_loads_no_console_errors(page: Page, live_server_url: str) -> None:
    """Covers: H1/H2 — SPA loads with [data-testid="home-page"] and no broken-resource errors.

    Complements B-SHELL-001 in test_browser_smoke.py. This test repeats the
    broken-resource check specifically for the Milestone F build (pdomain-ui 0.7.0
    + ComputeTargetPanel/UpdatePanel wiring) to confirm no new resource errors
    were introduced by the Compute + Updates panel additions.

    /api/suite/update is intercepted before goto() (returning update_available:false)
    so the test does not depend on the live version-check endpoint.
    """
    # Intercept the update check before the page loads so the hook sees a
    # deterministic no-update payload rather than a real network call.
    page.route(
        "**/api/suite/update",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_UPDATE_NO_UPDATE),
        ),
    )

    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    broken = [e for e in errors if "Failed to load" in e or "404" in e]
    assert broken == [], (
        "SPA loaded with broken-resource console errors after Milestone F additions:\n" + "\n".join(broken)
    )


# ---------------------------------------------------------------------------
# H2 — Compute settings tab renders panel + CPU device option
# ---------------------------------------------------------------------------


def test_compute_panel_visible_and_lists_cpu(page: Page, live_server_url: str) -> None:
    """Covers: H2 — opening the settings dock → Compute tab shows compute-target-panel
    with a cpu device option.

    /api/suite/device is intercepted to return a synthetic local-mode payload so
    ComputeTargetPanel renders (it returns null when mode != "local"). The intercept
    must be wired before page.goto() because the hook fetches on component mount.
    """
    # Intercept /api/suite/device BEFORE the page loads so the hook sees the payload
    # on its first (mount-time) fetch.
    page.route(
        "**/api/suite/device",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_DEVICE_LOCAL_CPU_ONLY),
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the settings utility dock via the gear trigger.
    trigger = page.get_by_test_id("settings-slot-trigger")
    expect(trigger).to_be_visible(timeout=5_000)
    trigger.click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Click the Compute settings tab.
    compute_tab = page.get_by_test_id("settings-modal-tab-compute")
    expect(compute_tab).to_be_visible(timeout=5_000)
    compute_tab.click()

    # Observable: settings-modal-panel-compute is the active panel.
    expect(page.get_by_test_id("settings-modal-panel-compute")).to_be_visible(timeout=5_000)

    # Observable: compute-target-panel is rendered with a CPU device option.
    # ComputeTargetPanel only renders when info.mode === "local" — our intercept
    # ensures this condition is met.
    expect(page.get_by_test_id("compute-target-panel")).to_be_visible(timeout=5_000)
    expect(page.get_by_test_id("compute-device-option-cpu")).to_be_visible(timeout=3_000)

    # Bad-state: closing the dock hides the panel.
    page.get_by_test_id("slide-over-panel-close").click()
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# H2c — Header update-badge is visible when an update is available
# ---------------------------------------------------------------------------


def test_update_badge_visible_when_update_available(page: Page, live_server_url: str) -> None:
    """Covers: H2c — SimpleGuiHeader renders the update-badge when update_available is true.

    The badge lives in SimpleGuiHeader (pdomain-ui) and is only rendered when
    the /api/suite/update response carries update_available:true.  We intercept
    that route BEFORE page.goto() so the hook sees the update payload on its
    first (mount-time) fetch, ensuring the badge is present in the initial render.
    """
    # Intercept /api/suite/update before the page loads so the header badge
    # renders on mount rather than after an async update.
    page.route(
        "**/api/suite/update",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_UPDATE_AVAILABLE),
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Observable: the update-badge is visible in the header when an update is available.
    # SimpleGuiHeader only renders this element when update_available is true.
    expect(page.get_by_test_id("update-badge")).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# H2 — Updates settings tab renders the update panel
# ---------------------------------------------------------------------------


def test_updates_panel_visible(page: Page, live_server_url: str) -> None:
    """Covers: H2 — opening the settings dock → Updates tab shows update-panel.

    UpdatePanel always renders regardless of update_available (unlike
    ComputeTargetPanel which is mode-gated). We intercept /api/suite/update to
    return a known no-update payload to avoid non-determinism in the version check.
    """
    page.route(
        "**/api/suite/update",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_UPDATE_NO_UPDATE),
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the settings utility dock.
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Click the Updates settings tab.
    updates_tab = page.get_by_test_id("settings-modal-tab-updates")
    expect(updates_tab).to_be_visible(timeout=5_000)
    updates_tab.click()

    # Observable: settings-modal-panel-updates is the active panel.
    expect(page.get_by_test_id("settings-modal-panel-updates")).to_be_visible(timeout=5_000)

    # Observable: update-panel is rendered inside the panel content.
    # UpdatePanel always renders (not mode-gated) so no extra intercept needed
    # beyond stopping non-deterministic network calls.
    expect(page.get_by_test_id("update-panel")).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# H2 — React Router sub-path renders a page component, not a JSON 404
# ---------------------------------------------------------------------------


def test_router_subpath_renders_page_not_json(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: H2 — /jobs/:id renders results-page via React Router, not a raw JSON 404.

    The FastAPI catch-all serves the SPA index for any unknown path; React Router
    then takes over client-side. This test confirms the catch-all + React Router
    contract is intact for the Milestone F build (pdomain-ui 0.7.0).

    Uses seeded_job_id so the backend /api/jobs/{id} returns real project data
    rather than a 404 that would leave the results-page in an error state.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")

    # Observable: React Router mounted the results-page, not the home page.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("home-page")).to_have_count(0)

    # Observable: raw JSON "Not Found" from FastAPI must NOT be visible.
    # If the catch-all is broken, FastAPI returns {"detail":"Not Found"} as plain HTML.
    content = page.content()
    assert '"Not Found"' not in content, (
        "FastAPI returned a raw JSON 404 instead of the SPA index — the React Router catch-all may be broken."
    )

    # Observable: the document title is non-empty (SPA has initialised + set title).
    assert page.title() != "", "Expected a non-empty page title after routing to /jobs/:id"
