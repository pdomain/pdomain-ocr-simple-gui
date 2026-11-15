"""Browser contracts for the Storage settings panel.

The e2e server deliberately uses authoritative environment overrides for its
storage roots. The Storage panel must show those effective roots and prevent a
data move that could not take effect. Model-cache choices are persisted as a
restart-bound preference: the active provider paths do not move in-process.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect
from pydantic import TypeAdapter

pytestmark = [pytest.mark.slow, pytest.mark.e2e]

_JSON_OBJECT = TypeAdapter(dict[str, object])
_STRING_MAP = TypeAdapter(dict[str, str])


def _json_object(response: httpx.Response) -> dict[str, object]:
    """Return a successful JSON object response with checked string keys."""
    _ = response.raise_for_status()
    return _JSON_OBJECT.validate_json(response.content)


def _string_map(value: object, *, field: str) -> dict[str, str]:
    """Validate one string-to-string API field before using it in assertions."""
    try:
        return _STRING_MAP.validate_python(value)
    except ValueError as error:
        raise AssertionError(f"Expected {field} to map strings to strings, got {value!r}") from error


def _locations(base_url: str) -> dict[str, object]:
    """Read the storage report that the visible panel renders."""
    return _json_object(httpx.get(f"{base_url}/api/locations", timeout=5.0))


def _open_storage_panel(page: Page, base_url: str) -> Locator:
    """Navigate to Settings and return the visible Storage panel."""
    _ = page.goto(base_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("settings-slot-trigger").click()
    storage_tab = page.get_by_test_id("settings-modal-tab-jobs")
    expect(storage_tab).to_be_visible(timeout=10_000)
    expect(storage_tab).to_have_text("Storage")
    storage_tab.click()
    panel = page.get_by_role("tabpanel", name="Storage")
    expect(panel).to_be_visible(timeout=10_000)
    return panel


def _reopen_storage_panel(page: Page) -> Locator:
    """Open the Storage panel after a browser reload."""
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("settings-slot-trigger").click()
    page.get_by_test_id("settings-modal-tab-jobs").click()
    panel = page.get_by_role("tabpanel", name="Storage")
    expect(panel).to_be_visible(timeout=10_000)
    return panel


def test_storage_shows_authoritative_roots_and_blocks_data_move(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Storage shows effective override roots and will not plan an overridden move."""
    report = _locations(live_server_url)
    paths = _string_map(report["paths"], field="paths")
    overrides = _string_map(report["overrides"], field="overrides")
    expected = {
        "projects": (e2e_data_root / "projects", "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"),
        "outputs": (e2e_data_root / "outputs", "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT"),
        "uploads": (e2e_data_root / "uploads", "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT"),
        "jobs": (e2e_data_root / "jobs_meta", "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT"),
    }
    panel = _open_storage_panel(page, live_server_url)

    for name, (root, variable) in expected.items():
        assert paths[name] == str(root)
        assert overrides[name] == variable
        expect(panel.get_by_text(name, exact=True)).to_be_visible()
        expect(panel.get_by_text(str(root), exact=True)).to_be_visible()
        expect(panel.get_by_text(variable, exact=True)).to_be_visible()

    page.get_by_label("New data folder").fill(str(e2e_data_root / "move-request"))
    expect(page.get_by_role("button", name="Review data move")).to_be_disabled()


def test_model_cache_preference_persists_but_needs_restart(
    page: Page, live_server_url: str, e2e_data_root: Path
) -> None:
    """Saving a model-cache preference survives reload without moving live cache paths."""
    before = _locations(live_server_url)
    active_paths = _string_map(before["model_paths"], field="model_paths")
    requested = str(e2e_data_root / "requested-model-cache")
    _ = _open_storage_panel(page, live_server_url)

    page.get_by_label("Model cache folder").fill(requested)
    page.get_by_role("button", name="Save model location").click()
    expect(page.get_by_role("status")).to_have_text("Restart the app to apply the new model location.")

    persisted = _json_object(httpx.get(f"{live_server_url}/api/prefs", timeout=5.0))
    assert persisted["model_cache_location"] == requested
    changed = _locations(live_server_url)
    assert changed["requested_model_cache"] == requested
    assert changed["model_cache_restart_required"] is True
    assert _string_map(changed["model_paths"], field="model_paths") == active_paths

    _ = page.reload()
    _ = _reopen_storage_panel(page)
    expect(page.get_by_label("Model cache folder")).to_have_value(requested)
    expect(page.get_by_role("status")).to_have_text("Restart the app to apply the new model location.")

    reloaded = _locations(live_server_url)
    assert reloaded["requested_model_cache"] == requested
    assert reloaded["model_cache_restart_required"] is True
    assert _string_map(reloaded["model_paths"], field="model_paths") == active_paths
