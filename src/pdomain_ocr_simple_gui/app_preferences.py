"""App-owned preferences and a suite-compatible preference proxy."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from uuid import uuid4

from filelock import FileLock
from pydantic import TypeAdapter, ValidationError

if TYPE_CHECKING:
    from pathlib import Path

    from pdomain_ops.suite.prefs import PrefsAdapter
    from pdomain_ops.suite.types import CommonUIPrefs, UIPrefs


_OBJECT_ADAPTER = TypeAdapter(dict[str, object])


class AppPreferencesError(RuntimeError):
    """Raised when existing app preferences cannot be read without data loss."""


class AppPreferencesStore:
    """Persist this app's preference section separately from suite preferences."""

    def __init__(self, path: Path) -> None:
        self._path: Path = path
        self._lock: FileLock = FileLock(str(path.with_suffix(".lock")))

    def _read_payload(self) -> dict[str, object]:
        try:
            raw = _OBJECT_ADAPTER.validate_json(self._path.read_text(encoding="utf-8"))
        except (OSError, ValidationError):
            raise AppPreferencesError(f"Cannot read app preferences: {self._path}") from None
        if "app" not in raw:
            raise AppPreferencesError(f"App preferences have no app section: {self._path}")
        try:
            return _OBJECT_ADAPTER.validate_python(raw["app"])
        except ValidationError:
            raise AppPreferencesError(f"App preferences have an invalid app section: {self._path}") from None

    def _write_payload(self, payload: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        staged = self._path.parent / f".{self._path.name}.{uuid4().hex}.tmp"
        try:
            _ = staged.write_text(json.dumps({"app": payload}, indent=2), encoding="utf-8")
            os.replace(staged, self._path)
        finally:
            staged.unlink(missing_ok=True)

    def read_app(self, legacy_payload: dict[str, object] | None = None) -> dict[str, object]:
        """Read app preferences, copying a legacy suite section once when needed."""
        with self._lock:
            if self._path.exists():
                return self._read_payload()
            payload = dict(legacy_payload) if legacy_payload is not None else {}
            self._write_payload(payload)
            return payload

    def write_app(self, payload: dict[str, object]) -> None:
        """Replace this app's preference section."""
        with self._lock:
            if self._path.exists():
                _ = self._read_payload()
            self._write_payload(dict(payload))


class AppPrefsAdapterProxy:
    """Present app-owned preferences through the suite ``PrefsAdapter`` shape."""

    def __init__(self, app_id: str, app_store: AppPreferencesStore, suite_prefs: PrefsAdapter) -> None:
        self._app_id: str = app_id
        self._app_store: AppPreferencesStore = app_store
        self._suite_prefs: PrefsAdapter = suite_prefs

    def read(self) -> UIPrefs:
        """Return shared preferences with this app's section from app-owned storage."""
        snapshot = self._suite_prefs.read()
        legacy_payload = snapshot.apps.get(self._app_id)
        app_payload = self._app_store.read_app(
            dict(legacy_payload) if isinstance(legacy_payload, dict) else None
        )
        snapshot.apps[self._app_id] = app_payload
        return snapshot

    def write_common(self, common: CommonUIPrefs) -> None:
        """Keep shared common UI preferences in the suite preference file."""
        self._suite_prefs.write_common(common)

    def write_app(self, app_id: str, payload: dict[str, object]) -> None:
        """Write only this app's section locally; delegate other app sections."""
        if app_id == self._app_id:
            self._app_store.write_app(payload)
            return
        self._suite_prefs.write_app(app_id, payload)
