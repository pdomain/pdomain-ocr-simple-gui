"""Tests for the app-owned preferences adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from pdomain_ops.suite.prefs import LocalFilePrefs
from pdomain_ops.suite.types import CommonUIPrefs

from pdomain_ocr_simple_gui.app_preferences import (
    AppPreferencesError,
    AppPreferencesStore,
    AppPrefsAdapterProxy,
)
from pdomain_ocr_simple_gui.constants import APP_ID


def test_proxy_copies_only_this_apps_legacy_preferences_once(tmp_path: Path) -> None:
    suite = LocalFilePrefs(root=tmp_path / "suite.json")
    suite.write_common(CommonUIPrefs(theme="light"))
    suite.write_app(APP_ID, {"default_engine": "tesseract"})
    suite.write_app("another-app", {"keep": "shared"})
    store = AppPreferencesStore(tmp_path / "config" / "preferences.json")
    proxy = AppPrefsAdapterProxy(APP_ID, store, suite)

    snapshot = proxy.read()

    assert snapshot.common.theme == "light"
    assert snapshot.apps[APP_ID]["default_engine"] == "tesseract"
    assert snapshot.apps["another-app"] == {"keep": "shared"}
    assert store.read_app() == {"default_engine": "tesseract"}


def test_proxy_keeps_app_preferences_out_of_suite_file(tmp_path: Path) -> None:
    suite = LocalFilePrefs(root=tmp_path / "suite.json")
    suite.write_app(APP_ID, {"default_engine": "doctr"})
    store = AppPreferencesStore(tmp_path / "config" / "preferences.json")
    proxy = AppPrefsAdapterProxy(APP_ID, store, suite)
    _ = proxy.read()

    proxy.write_app(APP_ID, {"default_engine": "tesseract"})
    proxy.write_app("another-app", {"keep": "shared"})

    assert store.read_app() == {"default_engine": "tesseract"}
    suite_snapshot = suite.read()
    assert suite_snapshot.apps[APP_ID] == {"default_engine": "doctr"}
    assert suite_snapshot.apps["another-app"] == {"keep": "shared"}


def test_malformed_app_preferences_are_preserved_for_recovery(tmp_path: Path) -> None:
    path = tmp_path / "config" / "preferences.json"
    path.parent.mkdir()
    path.write_text("not-json", encoding="utf-8")
    store = AppPreferencesStore(path)

    with pytest.raises(AppPreferencesError):
        _ = store.read_app()
    with pytest.raises(AppPreferencesError):
        store.write_app({"default_engine": "doctr"})

    assert path.read_text(encoding="utf-8") == "not-json"
