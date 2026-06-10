"""Tests that a contended prefs file lock can never hang the app.

Root cause guarded here: ``pdomain_ops.suite.prefs.LocalFilePrefs`` acquires a
``filelock.FileLock`` with a finite timeout (DEFAULT_LOCK_TIMEOUT = 5s as of
v0.10.0). When another process holds that lock -- e.g. an xdist worker or an e2e
server subprocess orphaned by a previously-killed ``pytest -n auto`` run -- the
next ``read()``/``write_app()`` raises ``PrefsLockTimeout`` after the timeout
instead of blocking forever.

``GET``/``PUT /api/prefs`` must catch ``PrefsLockTimeout`` and degrade
gracefully (GET → defaults, PUT → log + still return the merged payload)
rather than surfacing a raw 500 to the caller.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


def _hold_lock(lock_path: str, seconds: float) -> subprocess.Popen[bytes]:
    """Spawn a process that grabs *lock_path* and holds it for *seconds*."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (f"import filelock,time; l=filelock.FileLock({lock_path!r}); l.acquire(); time.sleep({seconds})"),
        ]
    )
    # Give the holder a beat to actually acquire the lock.
    time.sleep(1.5)
    return proc


@pytest.mark.asyncio
async def test_get_prefs_returns_defaults_when_lock_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/prefs returns 200 with defaults promptly when the prefs lock is held.

    This proves that the route catches PrefsLockTimeout and degrades gracefully
    instead of blocking or raising a 500.
    """
    from pdomain_ops.suite.prefs import LocalFilePrefs

    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import app

    prefs_path = tmp_path / "ui-prefs.json"
    lock_path = str(prefs_path.with_suffix(".json.lock"))
    # Use a short lock_timeout so the test runs fast.
    adapter = LocalFilePrefs(root=prefs_path, lock_timeout=2.0)
    monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

    holder = _hold_lock(lock_path, seconds=30)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            start = time.monotonic()
            resp = await ac.get("/api/prefs")
            elapsed = time.monotonic() - start

        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        assert elapsed < 10.0, f"GET /api/prefs blocked {elapsed:.1f}s on a held lock"
        # Should return defaults when lock is contended
        assert resp.json()["default_engine"] == "doctr"
    finally:
        holder.kill()
        holder.wait()


@pytest.mark.asyncio
async def test_put_prefs_returns_success_when_lock_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PUT /api/prefs returns 200 promptly when the prefs lock is held.

    The write degrades gracefully (lock contention is logged, merged payload is
    returned) instead of raising a 500. The caller receives the merged prefs so
    the UI can stay consistent even though the write was not persisted.
    """
    from pdomain_ops.suite.prefs import LocalFilePrefs

    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import app

    prefs_path = tmp_path / "ui-prefs.json"
    lock_path = str(prefs_path.with_suffix(".json.lock"))
    adapter = LocalFilePrefs(root=prefs_path, lock_timeout=2.0)
    monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

    holder = _hold_lock(lock_path, seconds=30)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            start = time.monotonic()
            resp = await ac.put(
                "/api/prefs",
                json={"default_engine": "tesseract"},
                headers={"Content-Type": "application/json"},
            )
            elapsed = time.monotonic() - start

        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        assert elapsed < 10.0, f"PUT /api/prefs blocked {elapsed:.1f}s on a held lock"
        # The merged payload should reflect the requested change
        assert resp.json()["default_engine"] == "tesseract"
    finally:
        holder.kill()
        holder.wait()


@pytest.mark.asyncio
async def test_lifespan_wires_local_file_prefs(monkeypatch: pytest.MonkeyPatch) -> None:
    """App startup wires LocalFilePrefs directly (no more TimeoutBoundedPrefs wrapper)."""
    from fastapi import FastAPI
    from pdomain_ops.suite.prefs import LocalFilePrefs

    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import lifespan

    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")
    async with lifespan(FastAPI()):
        adapter = app_mod.get_prefs_adapter()
        assert isinstance(adapter, LocalFilePrefs), (
            f"lifespan must wire LocalFilePrefs, got {type(adapter).__name__}"
        )
