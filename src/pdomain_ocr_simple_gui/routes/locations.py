"""Report effective locations and migrate app-owned data through an exclusive gate."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from fastapi import APIRouter, Depends, HTTPException, Request
from pdomain_ops.suite.prefs import PrefsLockTimeout
from pydantic import BaseModel, ConfigDict, Field

from pdomain_ocr_simple_gui.activity_gate import StorageBusyError, StorageGate
from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.cache_configuration import effective_model_paths, startup_state
from pdomain_ocr_simple_gui.locations import LocationConfigError, get_locations
from pdomain_ocr_simple_gui.migration import (
    MigrationBlockedError,
    MigrationCommitError,
    build_migration_plan,
    execute_migration,
)

if TYPE_CHECKING:
    from pdomain_ocr_simple_gui.locations import AppLocations

router = APIRouter(prefix="/api/locations", tags=["locations"], dependencies=[Depends(require_token)])
logger = logging.getLogger(__name__)


class LocationReport(BaseModel):
    """Effective paths and their controlling environment overrides."""

    paths: dict[str, str]
    overrides: dict[str, str]
    legacy_data_present: bool
    migration_in_progress: bool
    installation: dict[str, str]
    model_paths: dict[str, str]
    requested_model_cache: str
    model_cache_restart_required: bool


class MigrationRequest(BaseModel):
    """Choose the destination data directory without erasing original data."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    destination: str = Field(min_length=1, max_length=4096)


class MigrationPreview(BaseModel):
    """Show selected jobs and source entries that migration will retain."""

    destination: str
    projects: list[str]
    retained_items: list[str]


class MigrationReply(BaseModel):
    """Report the committed location and any retained preference warning."""

    data_root: str
    project_count: int
    originals_preserved: bool = True
    preference_warning: str | None = None


def _gate(request: Request) -> StorageGate:
    app: object = request.scope.get("app")
    state: object = getattr(app, "state", None)
    value: object = getattr(state, "storage_gate", None)
    if not isinstance(value, StorageGate):
        raise HTTPException(status_code=503, detail="Storage migration is unavailable")
    return value


def _locations() -> AppLocations:
    try:
        return get_locations()
    except LocationConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _installed_executable(command: str, fallback: Path) -> str:
    """Report an existing executable without running it."""
    discovered = shutil.which(command)
    if discovered:
        return discovered
    if fallback.is_file() and os.access(fallback, os.X_OK):
        return str(fallback)
    return ""


def _installation_paths() -> dict[str, str]:
    """Find native entry points even when launched with a minimal PATH."""
    suffix = ".exe" if sys.platform == "win32" else ""
    destination = next(
        (
            os.environ[key]
            for key in ("UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME")
            if os.environ.get(key)
        ),
        None,
    )
    if destination is None:
        data_home = os.environ.get("XDG_DATA_HOME")
        destination = str(Path(data_home) / "../bin") if data_home else str(Path.home() / ".local/bin")
    launcher = ""
    if sys.executable:
        launcher = _installed_executable(
            "pdomain-ocr-simple-gui-desktop",
            Path(sys.executable).with_name("pdomain-ocr-simple-gui-desktop" + suffix),
        )
    return {
        "app_environment": sys.prefix,
        "python": sys.executable,
        "python_runtime": sys.base_prefix,
        "desktop_launcher": launcher,
        "uv": _installed_executable("uv", Path(destination) / ("uv" + suffix)),
    }


@router.get("", response_model=LocationReport)
async def report_locations(request: Request) -> LocationReport:
    """Show current app paths without creating or moving data."""
    locations = await asyncio.to_thread(_locations)
    from pdomain_ocr_simple_gui.app import get_prefs_adapter
    from pdomain_ocr_simple_gui.constants import APP_ID

    adapter = get_prefs_adapter()
    requested = ""
    prefs_available = False
    if adapter is not None:
        try:
            prefs = await asyncio.to_thread(adapter.read)
        except PrefsLockTimeout:
            logger.warning("Preferences are busy; reporting effective paths without pending cache settings")
        else:
            prefs_available = True
            app_prefs: dict[str, object] = dict(prefs.apps.get(APP_ID, {}))
            candidate = app_prefs.get("model_cache_location", "")
            requested = candidate if isinstance(candidate, str) else ""
    return LocationReport(
        paths={
            "config": str(locations.config_root),
            "data": str(locations.data_root),
            "state": str(locations.state_root),
            "cache": str(locations.cache_root),
            "projects": str(locations.projects_root),
            "uploads": str(locations.uploads_root),
            "outputs": str(locations.outputs_root),
            "jobs": str(locations.jobs_root),
        },
        overrides=dict(locations.overrides),
        legacy_data_present=locations.has_legacy_data,
        migration_in_progress=_gate(request).migrating,
        installation=_installation_paths(),
        model_paths=effective_model_paths(),
        requested_model_cache=requested,
        model_cache_restart_required=prefs_available and requested != startup_state.location,
    )


@router.post("/plan", response_model=MigrationPreview)
async def preview_migration(body: MigrationRequest) -> MigrationPreview:
    """Validate a proposed move and list selected app-owned jobs."""
    try:
        plan = await asyncio.to_thread(
            build_migration_plan, _locations(), Path(body.destination).expanduser()
        )
    except MigrationBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MigrationPreview(
        destination=str(plan.destination),
        projects=list(plan.project_ids),
        retained_items=list(plan.retained_items),
    )


@router.post("/migrate", response_model=MigrationReply)
async def migrate_data(request: Request, body: MigrationRequest) -> MigrationReply:
    """Copy and verify data before switching locations while other work is blocked."""
    gate = _gate(request)
    try:
        with gate.exclusive():
            plan = await asyncio.to_thread(
                build_migration_plan, _locations(), Path(body.destination).expanduser()
            )
            result = await asyncio.to_thread(execute_migration, plan, is_active=lambda: gate.active_count > 0)
    except (StorageBusyError, MigrationBlockedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MigrationCommitError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail=f"Data move failed; original files remain: {exc}"
        ) from exc
    return MigrationReply(
        data_root=str(result.data_root),
        project_count=len(result.project_ids),
        preference_warning=result.preference_error,
    )
