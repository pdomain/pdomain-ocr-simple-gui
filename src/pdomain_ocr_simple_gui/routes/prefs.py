"""Prefs routes — GET/PUT /api/prefs via PrefsAdapter."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.models import AppPrefs, AppPrefsResponse

router = APIRouter(prefix="/api/prefs", tags=["prefs"])

_APP_ID = "pdomain-ocr-simple-gui"


def _validate_jobs_location(value: str) -> None:
    """Validate a non-empty jobs_location: it must be creatable and writable.

    Empty is always valid (means: fall back to env var / shipped default).
    A non-empty value is expanded (``~``), resolved, ``mkdir(parents=True,
    exist_ok=True)``-ed, and probed for writability.  Raises HTTPException 400
    with a clear message on any failure so the PUT handler can surface it.
    """
    if not value:
        return
    target = Path(value).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".pd-ocr-write-probe"
        _ = probe.write_text("")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"jobs location is not writable: {target} ({exc.strerror or exc})",
        ) from exc


@router.get("", response_model=AppPrefsResponse, dependencies=[Depends(require_token)])
async def get_prefs() -> AppPrefsResponse:
    """Return the app prefs (plus the resolved effective jobs location)."""
    from pdomain_ocr_simple_gui.app import get_prefs_adapter
    from pdomain_ocr_simple_gui.storage import _projects_root

    adapter = get_prefs_adapter()
    if adapter is None:
        base = AppPrefs()
    else:
        raw = adapter.read().apps.get(_APP_ID, {})
        base = AppPrefs.model_validate(raw) if raw else AppPrefs()
    return AppPrefsResponse(
        **base.model_dump(),
        effective_jobs_location=str(_projects_root()),
    )


@router.put("", response_model=AppPrefs, dependencies=[Depends(require_token)])
async def put_prefs(body: Annotated[dict[str, Any], Body()]) -> AppPrefs:
    """Persist app prefs via a read-modify-WRITE merge (best-effort if no adapter).

    The body is treated as a PARTIAL patch: only the keys it carries are
    updated; every previously-saved field is read back and preserved.  This
    makes the endpoint clobber-proof — a client that sends only the field it
    changed (e.g. ``{"ui_prefs": {...}}`` from the appearance toggle, or
    ``{"default_engine": "doctr"}``) can never wipe sibling prefs back to
    their type defaults.  ``effective_jobs_location`` is read-only and ignored
    if sent.
    """
    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    adapter = get_prefs_adapter()

    # Read the currently-stored app prefs (defaults if none/no adapter).
    if adapter is not None:
        raw = adapter.read().apps.get(_APP_ID, {})
        existing = AppPrefs.model_validate(raw) if raw else AppPrefs()
    else:
        existing = AppPrefs()

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

    _validate_jobs_location(merged.jobs_location)

    if adapter is not None:
        adapter.write_app(_APP_ID, merged.model_dump())
    return merged
