"""Prefs routes — GET/PUT /api/prefs via PrefsAdapter."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.locations import is_within_installation
from pdomain_ocr_simple_gui.models import AppPrefs, AppPrefsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prefs", tags=["prefs"])

_APP_ID = "pdomain-ocr-simple-gui"


def _validate_storage_destination(value: str, *, model_cache: bool = False) -> None:
    """Reject new storage choices that removal would delete, without writing."""
    if not value:
        return
    target = Path(value).expanduser()
    if model_cache and not target.is_absolute():
        raise HTTPException(status_code=400, detail="Model cache location must be an absolute path")
    paths = [target]
    if model_cache:
        paths.extend((target / "doctr", target / "huggingface/hub", target / "torch/hub"))
    try:
        if any(is_within_installation(path) for path in paths):
            raise HTTPException(status_code=400, detail="Choose a folder outside the installed application")
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Cannot resolve the requested storage folder") from exc


def _validate_jobs_location(value: str) -> None:
    """Validate a non-empty jobs_location: it must be creatable and writable.

    Empty is always valid (means: fall back to env var / shipped default).
    A non-empty value is expanded (``~``), resolved, ``mkdir(parents=True,
    exist_ok=True)``-ed, and probed for writability.  Raises HTTPException 400
    with a clear message on any failure so the PUT handler can surface it.
    """
    if not value:
        return
    _validate_storage_destination(value)
    target = Path(value).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f".pd-ocr-write-probe-{uuid4().hex}"
        with probe.open("x", encoding="utf-8"):
            pass
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"jobs location is not writable: {target} ({exc.strerror or exc})",
        ) from exc


@router.get("", response_model=AppPrefsResponse, dependencies=[Depends(require_token)])
async def get_prefs() -> AppPrefsResponse:
    """Return the app prefs (plus the resolved effective jobs location).

    If the prefs file lock cannot be acquired in time (PrefsLockTimeout from
    pdomain-ops v0.10.0+), degrades gracefully to defaults rather than raising
    a 500 — prefs are optional and must never break the app.
    """
    from pdomain_ops.suite.prefs import PrefsLockTimeout

    from pdomain_ocr_simple_gui.app import get_prefs_adapter
    from pdomain_ocr_simple_gui.storage import get_projects_root

    adapter = get_prefs_adapter()
    if adapter is None:
        base = AppPrefs()
    else:
        try:
            prefs_data = await asyncio.to_thread(adapter.read)
            app_data: dict[str, object] = dict(prefs_data.apps.get(_APP_ID, {}))
        except PrefsLockTimeout:
            logger.warning(
                "Prefs lock contended on GET; returning default prefs",
                extra={"context": "get_prefs", "app_id": _APP_ID},
            )
            app_data = {}
        base = AppPrefs.model_validate(app_data) if app_data else AppPrefs()
    return AppPrefsResponse.model_validate(
        {
            **base.model_dump(),
            "effective_jobs_location": str(get_projects_root()),
        }
    )


@router.put("", response_model=AppPrefs, dependencies=[Depends(require_token)])
async def put_prefs(body: Annotated[dict[str, object], Body()]) -> AppPrefs:
    """Persist a partial preference patch or report an unavailable store.

    The body is treated as a PARTIAL patch: only the keys it carries are
    updated; every previously-saved field is read back and preserved.  This
    makes the endpoint clobber-proof — a client that sends only the field it
    changed (e.g. ``{"ui_prefs": {...}}`` from the appearance toggle, or
    ``{"default_engine": "doctr"}``) can never wipe sibling prefs back to
    their type defaults.  ``effective_jobs_location`` is read-only and ignored
    if sent.
    """
    from pdomain_ops.suite.prefs import PrefsLockTimeout

    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    adapter = get_prefs_adapter()
    if adapter is None:
        raise HTTPException(status_code=503, detail="Preferences are unavailable. No changes were saved.")

    try:
        prefs_data = await asyncio.to_thread(adapter.read)
        app_data: dict[str, object] = dict(prefs_data.apps.get(_APP_ID, {}))
    except PrefsLockTimeout as exc:
        logger.warning("Prefs lock contended on PUT read; preserving stored settings")
        raise HTTPException(
            status_code=503, detail="Preferences are busy. No changes were saved; retry."
        ) from exc
    existing = AppPrefs.model_validate(app_data) if app_data else AppPrefs()

    # Merge at the dict level: provided keys win, all others keep their stored
    # value. Drop the read-only echo field so a round-tripped GET body can't
    # reach the model. Re-validate so a bad partial value (wrong type) still
    # yields a 422 and nested fields (ui_prefs) coerce to their model type.
    merged_dict = existing.model_dump()
    merged_dict.update({k: v for k, v in body.items() if k != "effective_jobs_location"})
    try:
        merged = AppPrefs.model_validate(merged_dict)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    jobs_changed = merged.jobs_location != existing.jobs_location
    models_changed = merged.model_cache_location != existing.model_cache_location
    # Preflight both choices before either writability probe can create a folder.
    # Existing legacy choices remain readable so users can migrate out of them.
    if jobs_changed:
        await asyncio.to_thread(_validate_storage_destination, merged.jobs_location)
    if models_changed:
        await asyncio.to_thread(_validate_storage_destination, merged.model_cache_location, model_cache=True)
    if jobs_changed:
        await asyncio.to_thread(_validate_jobs_location, merged.jobs_location)
    if models_changed:
        await asyncio.to_thread(_validate_jobs_location, merged.model_cache_location)

    try:
        await asyncio.to_thread(adapter.write_app, _APP_ID, merged.model_dump())
    except PrefsLockTimeout as exc:
        logger.warning("Prefs lock contended on PUT; change was not saved")
        raise HTTPException(
            status_code=503, detail="Preferences are busy. No changes were saved; retry."
        ) from exc
    return merged
