"""Prefs routes — GET/PUT /api/prefs via PrefsAdapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.models import AppPrefs, AppPrefsResponse

logger = logging.getLogger(__name__)

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
            app_data: dict[str, object] = dict(adapter.read().apps.get(_APP_ID, {}))
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
    """Persist app prefs via a read-modify-WRITE merge (best-effort if no adapter).

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

    # Read the currently-stored app prefs (defaults if none/no adapter).
    # If the lock is contended, degrade to defaults for the merge base so we
    # can still apply the PUT body and return a valid merged response.
    if adapter is not None:
        try:
            app_data: dict[str, object] = dict(adapter.read().apps.get(_APP_ID, {}))
        except PrefsLockTimeout:
            logger.warning(
                "Prefs lock contended on PUT read; using defaults as merge base",
                extra={"context": "put_prefs.read", "app_id": _APP_ID},
            )
            app_data = {}
        existing = AppPrefs.model_validate(app_data) if app_data else AppPrefs()
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
        try:
            adapter.write_app(_APP_ID, merged.model_dump())
        except PrefsLockTimeout:
            # Lock is contended: log and return the merged payload anyway so the
            # UI stays consistent. The write was not persisted (best-effort), but
            # the caller receives a valid merged response rather than a 500.
            logger.warning(
                "Prefs lock contended on PUT; write not persisted (best-effort)",
                extra={"context": "put_prefs", "app_id": _APP_ID},
            )
    return merged
