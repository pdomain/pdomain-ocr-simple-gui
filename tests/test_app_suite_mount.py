"""Suite mount wiring: device prefs must persist under the real app_id.

Before this fix, ``app.py`` called ``mount_routes(_app)`` with no
``adapters``/``suite_app``, so ``mount_device_routes`` defaulted
``app_id="unknown"`` — every compute-device preference set via Settings was
silently written to ``apps["unknown"]`` instead of
``apps["pdomain-ocr-simple-gui"]``. These tests exercise the fix through the
real released pdomain-ops API (``mount_routes(adapters=, suite_app=)``), and
(Task 19) that the OCR dispatcher's device_resolver reads that same pref.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pdomain_ops.suite.prefs import LocalFilePrefs

import pdomain_ocr_simple_gui.app as app_mod
from pdomain_ocr_simple_gui.app import create_app, lifespan
from pdomain_ocr_simple_gui.constants import APP_ID

if TYPE_CHECKING:
    from pathlib import Path

    from pdomain_ops.suite.types import UIPrefs


def _prefs_snapshot(suite_data_root: Path) -> UIPrefs:
    """Read the ui-prefs.json snapshot written under *suite_data_root*."""
    return LocalFilePrefs(root=suite_data_root / "ui-prefs.json").read()


def test_device_put_persists_under_real_app_id(
    tmp_prefs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PUT /api/suite/device writes the pref under the app's real app_id.

    Also proves "unknown" was never touched — the pre-fix mount defaulted to
    app_id="unknown" for every device write.
    """
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    client = TestClient(create_app())

    resp = client.put("/api/suite/device", json={"scope": "app", "device": "cpu"})

    assert resp.status_code == 200
    snap = _prefs_snapshot(tmp_prefs)
    assert snap.apps.get(APP_ID, {}).get("compute_device") == "cpu"
    assert "unknown" not in snap.apps


@pytest.mark.asyncio
async def test_lifespan_migrates_unknown_device_pref_to_real_app_id(
    tmp_prefs: Path,
) -> None:
    """A pre-existing apps["unknown"].compute_device migrates to the real app_id.

    Simulates an install that hit the pre-fix "unknown" bug: seed the pref
    directly, then run app startup (``lifespan``) and confirm the value moved.

    ``PrefsAdapter`` (pdomain_ops.suite.prefs) exposes no delete primitive, so
    the migration clears the stray ``compute_device`` key from "unknown"
    rather than removing the whole section — an app section with no
    ``compute_device`` is otherwise inert.
    """
    seed_adapter = LocalFilePrefs(root=tmp_prefs / "ui-prefs.json")
    seed_adapter.write_app("unknown", {"compute_device": "cuda:0"})

    async with lifespan(FastAPI()):
        pass

    snap = _prefs_snapshot(tmp_prefs)
    assert snap.apps[APP_ID]["compute_device"] == "cuda:0"
    assert snap.apps.get("unknown", {}).get("compute_device") is None


@pytest.mark.asyncio
async def test_dispatcher_resolver_follows_suite_pref(
    tmp_prefs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LocalStageDispatcher's device_resolver reads the suite compute-device pref.

    The resolver is a closure over the module-level prefs adapter, not a
    value captured at dispatcher-construction time, so it must be re-read
    on every call — verified here by calling it directly after startup.
    """
    monkeypatch.delenv("PDOMAIN_OCR_FAKE_DISPATCHER", raising=False)
    seed_adapter = LocalFilePrefs(root=tmp_prefs / "ui-prefs.json")
    seed_adapter.write_app(APP_ID, {"compute_device": "cpu"})

    async with lifespan(FastAPI()):
        dispatcher = app_mod.get_dispatcher()
        assert dispatcher is not None
        assert dispatcher._device_resolver is not None
        assert dispatcher._device_resolver() == "cpu"
