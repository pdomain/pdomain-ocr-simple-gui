"""5.x — settings: jobs-location panel (env > pref > default).

Light single-test e2e: open Settings → Jobs panel, set a writable location
under the e2e tmp root, save, and assert success (no inline error).

Note on precedence: the e2e server sets ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT``,
and the env var WINS over the pref. So saving the pref does not change the
displayed "current location" here — this test asserts the SAVE path
(validation + 200), not a change in effective root. The env-wins / pref-used
precedence is covered by the backend unit tests in
``tests/test_jobs_location_pref.py``.

Marked ``slow`` and ``e2e`` — excluded from ``make test``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_settings_jobs_location_save(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Open Settings → Jobs, set a writable tmp location, save → no error."""
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the Settings surface (utility dock slide-over).
    page.get_by_test_id("settings-slot-trigger").click()

    # Switch to the app-injected Jobs panel tab.
    jobs_tab = page.get_by_test_id("settings-modal-tab-jobs")
    expect(jobs_tab).to_be_visible(timeout=10_000)
    jobs_tab.click()

    # The panel + input are visible.
    expect(page.get_by_test_id("settings-jobs-location-input")).to_be_visible(timeout=10_000)

    # Type a writable location under the e2e tmp root so validation succeeds
    # AND nothing escapes the tmp tree.
    target = str(e2e_data_root / "user_chosen_jobs")
    input_el = page.get_by_test_id("settings-jobs-location-input")
    input_el.fill(target)
    page.get_by_test_id("settings-jobs-location-save").click()

    # Success: no inline error surfaces, the Saved indicator appears, and the
    # directory was created.
    expect(page.get_by_test_id("settings-jobs-location-error")).not_to_be_visible(timeout=5_000)
    expect(page.get_by_test_id("settings-jobs-location-saved")).to_be_visible(timeout=10_000)
    assert (e2e_data_root / "user_chosen_jobs").is_dir()
