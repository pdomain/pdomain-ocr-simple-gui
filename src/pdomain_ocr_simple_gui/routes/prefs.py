"""Prefs routes — GET/PUT /api/prefs via PrefsAdapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.models import AppPrefs

router = APIRouter(prefix="/api/prefs", tags=["prefs"])

_APP_ID = "pdomain-ocr-simple-gui"


@router.get("", response_model=AppPrefs, dependencies=[Depends(require_token)])
async def get_prefs() -> AppPrefs:
    """Return the app prefs, or defaults if no adapter/data present."""
    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    adapter = get_prefs_adapter()
    if adapter is None:
        return AppPrefs()
    raw = adapter.read().apps.get(_APP_ID, {})
    if not raw:
        return AppPrefs()
    return AppPrefs.model_validate(raw)


@router.put("", response_model=AppPrefs, dependencies=[Depends(require_token)])
async def put_prefs(body: AppPrefs) -> AppPrefs:
    """Persist app prefs via adapter (best-effort if no adapter)."""
    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    adapter = get_prefs_adapter()
    if adapter is not None:
        adapter.write_app(_APP_ID, body.model_dump())
    return body
