"""Tests that a contended prefs file lock can never hang the app.

Root cause guarded here: ``pdomain_ops.suite.prefs.LocalFilePrefs`` acquires a
``filelock.FileLock`` with the default ``timeout=-1`` (block forever).  When
another process holds that lock — e.g. an xdist worker or e2e server subprocess
orphaned by a previously-killed ``pytest -n auto`` run — the next real
``read()``/``write_app()`` blocks indefinitely, hanging the whole request (and,
under xdist, appearing as a frozen unrelated test).

``build_prefs_adapter`` must wrap the real adapter so that a contended lock
degrades to defaults / best-effort within a bounded time instead of hanging.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.prefs_adapter import build_prefs_adapter


def _hold_lock(lock_path: str, seconds: float) -> subprocess.Popen[bytes]:
    """Spawn a process that grabs *lock_path* and holds it for *seconds*."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import filelock,time; l=filelock.FileLock({lock_path!r}); l.acquire(); time.sleep({seconds})",
        ]
    )
    # Give the holder a beat to actually acquire the lock.
    time.sleep(1.5)
    return proc


def test_read_does_not_hang_when_lock_is_held(tmp_path: Path) -> None:
    """read() returns bounded defaults when the prefs lock is held elsewhere."""
    prefs_path = tmp_path / "ui-prefs.json"
    lock_path = str(prefs_path.with_suffix(".json.lock"))

    holder = _hold_lock(lock_path, seconds=30)
    try:
        adapter = build_prefs_adapter(prefs_path=prefs_path, lock_timeout=2.0)
        start = time.monotonic()
        result = adapter.read()
        elapsed = time.monotonic() - start

        # Must NOT block for the full hold; must return promptly with defaults.
        assert elapsed < 10.0, f"read() blocked {elapsed:.1f}s on a held lock"
        assert result.apps == {}
    finally:
        holder.kill()
        holder.wait()


def test_write_app_does_not_hang_when_lock_is_held(tmp_path: Path) -> None:
    """write_app() is best-effort and returns bounded when the lock is held."""
    prefs_path = tmp_path / "ui-prefs.json"
    lock_path = str(prefs_path.with_suffix(".json.lock"))

    holder = _hold_lock(lock_path, seconds=30)
    try:
        adapter = build_prefs_adapter(prefs_path=prefs_path, lock_timeout=2.0)
        start = time.monotonic()
        adapter.write_app("pdomain-ocr-simple-gui", {"default_engine": "tesseract"})
        elapsed = time.monotonic() - start

        assert elapsed < 10.0, f"write_app() blocked {elapsed:.1f}s on a held lock"
    finally:
        holder.kill()
        holder.wait()


def test_read_round_trips_normally_without_contention(tmp_path: Path) -> None:
    """With no contention the wrapper behaves like the real adapter."""
    prefs_path = tmp_path / "ui-prefs.json"
    adapter = build_prefs_adapter(prefs_path=prefs_path, lock_timeout=2.0)

    adapter.write_app("pdomain-ocr-simple-gui", {"default_engine": "tesseract"})
    result = adapter.read()

    assert result.apps["pdomain-ocr-simple-gui"]["default_engine"] == "tesseract"


@pytest.mark.asyncio
async def test_lifespan_wires_timeout_bounded_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """App startup wires the bounded adapter, so production never uses the raw lock."""
    from fastapi import FastAPI

    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import lifespan
    from pdomain_ocr_simple_gui.prefs_adapter import TimeoutBoundedPrefs

    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")
    async with lifespan(FastAPI()):
        adapter = app_mod.get_prefs_adapter()
        assert isinstance(adapter, TimeoutBoundedPrefs), (
            f"lifespan must wire TimeoutBoundedPrefs, got {type(adapter).__name__}"
        )


@pytest.mark.asyncio
async def test_get_prefs_route_does_not_hang_when_lock_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/prefs returns 200 promptly even when the prefs lock is held."""
    from httpx import ASGITransport, AsyncClient

    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import app

    prefs_path = tmp_path / "ui-prefs.json"
    lock_path = str(prefs_path.with_suffix(".json.lock"))
    adapter = build_prefs_adapter(prefs_path=prefs_path, lock_timeout=2.0)
    monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

    holder = _hold_lock(lock_path, seconds=30)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            start = time.monotonic()
            resp = await ac.get("/api/prefs")
            elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 10.0, f"GET /api/prefs blocked {elapsed:.1f}s on a held lock"
        assert resp.json()["default_engine"] == "doctr"
    finally:
        holder.kill()
        holder.wait()
