"""Timeout-bounded prefs adapter.

``pdomain_ops.suite.prefs.LocalFilePrefs`` guards every read/write with
``filelock.FileLock(...)`` using the default ``timeout=-1`` — block forever.
If any other process holds that lock (most commonly an xdist worker or e2e
server subprocess orphaned by a *killed* ``pytest -n auto`` run), the next real
``read()``/``write_app()`` blocks indefinitely and hangs the HTTP request.
Under xdist the freeze surfaces as an unrelated test "hanging" because output
is interleaved across workers.

``TimeoutBoundedPrefs`` is a drop-in ``PrefsAdapter`` that reads/writes the same
``ui-prefs.json`` file (the same on-disk format ``UIPrefs`` validates) but
acquires the file lock with a finite timeout.  On contention it degrades to
defaults (``read``) or a best-effort no-op (``write_*``), matching the app's
existing "prefs are optional, never break the app" philosophy (see
``app.lifespan`` and ``storage._jobs_location_pref``).

The unbounded lock in ``pdomain-ops`` should still be fixed at its source
(accept a ``timeout``); this is the in-repo containment so the app can never
wedge regardless of the library version installed.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import filelock
from pdomain_ops.suite.types import CommonUIPrefs, UIPrefs

if TYPE_CHECKING:
    from pathlib import Path

    from pdomain_ops.suite.prefs import PrefsAdapter

logger = logging.getLogger(__name__)

# Seconds to wait for the prefs file lock before giving up. Generous enough for
# normal contention between same-host requests, short enough that an orphaned
# lock can never wedge the app.
_DEFAULT_LOCK_TIMEOUT: float = 5.0


class TimeoutBoundedPrefs:
    """A local JSON ``PrefsAdapter`` whose file lock can never block forever.

    Reads and writes the suite's ``ui-prefs.json`` under a ``filelock.FileLock``
    acquired with a finite timeout.  On ``filelock.Timeout`` it degrades:

    * ``read`` -> ``UIPrefs()`` defaults
    * ``write_common`` / ``write_app`` -> best-effort no-op (logged)
    """

    _path: Path
    _lock_path: Path
    _lock_timeout: float

    def __init__(self, prefs_path: Path, lock_timeout: float = _DEFAULT_LOCK_TIMEOUT) -> None:
        self._path = prefs_path
        self._lock_path = prefs_path.with_suffix(".json.lock")
        self._lock_timeout = lock_timeout

    def _lock(self) -> filelock.FileLock:
        return filelock.FileLock(str(self._lock_path), timeout=self._lock_timeout)

    def _read_raw(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        try:
            loaded = cast("object", json.loads(self._path.read_text()))
        except (OSError, ValueError):
            return {}
        return cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}

    def _write_raw(self, data: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _ = self._path.write_text(json.dumps(data, indent=2, default=str))

    def read(self) -> UIPrefs:
        """Read prefs; return defaults if the lock cannot be acquired in time."""
        try:
            with self._lock():
                raw = self._read_raw()
        except filelock.Timeout:
            logger.warning(
                "Prefs lock contended; returning default prefs",
                extra={"context": "TimeoutBoundedPrefs.read()", "lock": str(self._lock_path)},
            )
            return UIPrefs()
        if not raw:
            return UIPrefs()
        return UIPrefs.model_validate(raw)

    def write_common(self, common: CommonUIPrefs) -> None:
        """Persist the common section; best-effort if the lock is contended."""
        try:
            with self._lock():
                data = self._read_raw()
                data["common"] = common.model_dump(mode="json")
                self._write_raw(data)
        except filelock.Timeout:
            logger.warning(
                "Prefs lock contended; skipping write_common (best-effort)",
                extra={"context": "TimeoutBoundedPrefs.write_common()"},
            )

    def write_app(self, app_id: str, payload: dict[str, object]) -> None:
        """Persist a per-app blob; best-effort if the lock is contended."""
        try:
            with self._lock():
                data = self._read_raw()
                apps = data.get("apps")
                if not isinstance(apps, dict):
                    apps = {}
                    data["apps"] = apps
                apps[app_id] = payload
                self._write_raw(data)
        except filelock.Timeout:
            logger.warning(
                "Prefs lock contended; skipping write_app (best-effort)",
                extra={"context": "TimeoutBoundedPrefs.write_app()", "app_id": app_id},
            )


def build_prefs_adapter(
    *,
    prefs_path: Path | None = None,
    lock_timeout: float = _DEFAULT_LOCK_TIMEOUT,
) -> PrefsAdapter:
    """Build the app's prefs adapter, bounded so a held lock can't hang requests.

    ``prefs_path`` defaults to the suite's resolved ``ui-prefs.json`` path
    (honouring ``PD_SUITE_DATA_DIR``); pass an explicit path in tests.
    """
    if prefs_path is None:
        from pdomain_ops.suite.paths import ui_prefs_json_path

        prefs_path = ui_prefs_json_path()
    return TimeoutBoundedPrefs(prefs_path, lock_timeout=lock_timeout)
