"""Resolve app-owned configuration, data, state, and cache locations."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import platformdirs
from filelock import FileLock
from pydantic import TypeAdapter, ValidationError

from pdomain_ocr_simple_gui.constants import APP_ID

if TYPE_CHECKING:
    from collections.abc import Mapping


_CONFIG_ROOT_ENV = "PD_OCR_SIMPLE_GUI_CONFIG_ROOT"
_DATA_ROOT_ENV = "PD_OCR_SIMPLE_GUI_DATA_ROOT"
_STATE_ROOT_ENV = "PD_OCR_SIMPLE_GUI_STATE_ROOT"
_CACHE_ROOT_ENV = "PD_OCR_SIMPLE_GUI_CACHE_ROOT"
_PROJECTS_ROOT_ENV = "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"
_UPLOADS_ROOT_ENV = "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT"
_OUTPUTS_ROOT_ENV = "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT"
_JOBS_ROOT_ENV = "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT"
_LOCATION_CONFIG_NAME = "data-location.json"
_OBJECT_ADAPTER = TypeAdapter(dict[str, object])


class LocationConfigError(RuntimeError):
    """Raised when an existing app location configuration cannot be trusted."""


@dataclass(frozen=True)
class LegacyLocations:
    """Known pre-app-owned locations, retained until migration is complete."""

    projects_root: Path
    uploads_root: Path
    outputs_root: Path
    jobs_root: Path


@dataclass(frozen=True)
class AppLocations:
    """Effective app locations and the legacy roots discovered alongside them."""

    config_root: Path
    data_root: Path
    state_root: Path
    cache_root: Path
    projects_root: Path
    uploads_root: Path
    outputs_root: Path
    jobs_root: Path
    preferences_path: Path
    location_config_path: Path
    legacy_locations: LegacyLocations
    has_legacy_data: bool
    overrides: Mapping[str, str]


def is_within_installation(path: Path) -> bool:
    """Identify destinations that app removal would recursively delete.

    Existing legacy roots may still be read and moved out. Call this guard
    before accepting a new storage choice or preparing removal, not while
    resolving the user's existing configuration.
    """
    if "\0" in str(path):
        raise ValueError("Storage path must not contain NUL")
    candidate = path.expanduser().resolve()
    removed_roots = [Path(sys.prefix).resolve()] if sys.prefix != sys.base_prefix else []
    if sys.platform == "darwin":
        applications = Path.home() / "Applications"
        removed_roots.extend(
            (applications / name).resolve() for name in ("OCR Simple GUI.app", "Uninstall OCR Simple GUI.app")
        )
    return any(candidate.is_relative_to(root) for root in removed_roots)


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else None


def _platform_path(kind: str) -> Path:
    if kind == "config":
        return Path(platformdirs.user_config_path(APP_ID, appauthor=False))
    if kind == "data":
        return Path(platformdirs.user_data_path(APP_ID, appauthor=False))
    if kind == "state":
        return Path(platformdirs.user_state_path(APP_ID, appauthor=False))
    return Path(platformdirs.user_cache_path(APP_ID, appauthor=False))


def _config_root() -> Path:
    return _env_path(_CONFIG_ROOT_ENV) or _platform_path("config")


def _location_config_path(config_root: Path) -> Path:
    return config_root / _LOCATION_CONFIG_NAME


def _read_configured_data_root(config_root: Path) -> Path | None:
    config_path = _location_config_path(config_root)
    if not config_path.exists():
        return None
    try:
        raw = _OBJECT_ADAPTER.validate_json(config_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        raise LocationConfigError(f"Cannot read location configuration: {config_path}") from None
    value = raw.get("data_root")
    if not isinstance(value, str) or not value:
        raise LocationConfigError(f"Location configuration has no data_root: {config_path}")
    return Path(value).expanduser()


def write_configured_data_root(data_root: Path) -> None:
    """Atomically save the app data root after migration has verified its copy."""
    try:
        inside_installation = is_within_installation(data_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise LocationConfigError("Cannot resolve the requested data folder") from exc
    if inside_installation:
        raise LocationConfigError("Choose a data folder outside the installed application")
    config_root = _config_root()
    config_path = _location_config_path(config_root)
    lock = FileLock(str(config_path.with_suffix(".lock")))
    with lock:
        if config_path.exists():
            _ = _read_configured_data_root(config_root)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        staged = config_path.parent / f".{config_path.name}.{uuid4().hex}.tmp"
        try:
            _ = staged.write_text(
                json.dumps({"data_root": str(data_root.expanduser())}, indent=2), encoding="utf-8"
            )
            os.replace(staged, config_path)
        finally:
            staged.unlink(missing_ok=True)


def _read_saved_jobs_location(config_root: Path) -> str:
    preferences_path = config_root / "preferences.json"
    if not preferences_path.exists():
        return ""
    try:
        raw = _OBJECT_ADAPTER.validate_json(preferences_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        raise LocationConfigError(f"Cannot read app preferences: {preferences_path}") from None
    try:
        app = _OBJECT_ADAPTER.validate_python(raw["app"])
    except KeyError:
        raise LocationConfigError(f"App preferences have no app section: {preferences_path}") from None
    except ValidationError:
        raise LocationConfigError(
            f"App preferences have an invalid app section: {preferences_path}"
        ) from None
    value = app.get("jobs_location")
    return value if isinstance(value, str) else ""


def _legacy_default_locations() -> LegacyLocations:
    legacy_app_data = Path.home() / ".local" / "share" / APP_ID
    return LegacyLocations(
        projects_root=Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects",
        uploads_root=legacy_app_data / "uploads",
        outputs_root=legacy_app_data / "outputs",
        jobs_root=legacy_app_data / "jobs",
    )


def _has_valid_project(root: Path) -> bool:
    try:
        return any((child / "project.json").is_file() for child in root.iterdir())
    except OSError:
        return False


def _has_entries(root: Path) -> bool:
    try:
        return any(root.iterdir())
    except OSError:
        return False


def _legacy_has_data(locations: LegacyLocations) -> bool:
    return (
        _has_valid_project(locations.projects_root)
        or _has_entries(locations.uploads_root)
        or _has_entries(locations.outputs_root)
        or _has_entries(locations.jobs_root)
    )


def _legacy_projects_root(legacy_jobs_location: str | None) -> Path:
    if legacy_jobs_location:
        return Path(legacy_jobs_location).expanduser()
    return _legacy_default_locations().projects_root


def get_locations(*, legacy_jobs_location: str | None = None) -> AppLocations:
    """Return effective roots without creating or moving any files."""
    config_root = _config_root()
    if legacy_jobs_location is None:
        legacy_jobs_location = _read_saved_jobs_location(config_root)
    configured_data_root = _read_configured_data_root(config_root)
    data_root_override = _env_path(_DATA_ROOT_ENV)
    data_root = data_root_override or configured_data_root or _platform_path("data")
    state_root = _env_path(_STATE_ROOT_ENV) or _platform_path("state")
    cache_root = _env_path(_CACHE_ROOT_ENV) or _platform_path("cache")
    legacy_defaults = _legacy_default_locations()
    legacy_locations = LegacyLocations(
        projects_root=_legacy_projects_root(legacy_jobs_location),
        uploads_root=legacy_defaults.uploads_root,
        outputs_root=legacy_defaults.outputs_root,
        jobs_root=legacy_defaults.jobs_root,
    )
    projects_override = _env_path(_PROJECTS_ROOT_ENV)
    uploads_override = _env_path(_UPLOADS_ROOT_ENV)
    outputs_override = _env_path(_OUTPUTS_ROOT_ENV)
    jobs_override = _env_path(_JOBS_ROOT_ENV)
    overrides = {
        name: env
        for name, env in (
            ("config", _CONFIG_ROOT_ENV),
            ("data", _DATA_ROOT_ENV),
            ("state", _STATE_ROOT_ENV),
            ("cache", _CACHE_ROOT_ENV),
            ("projects", _PROJECTS_ROOT_ENV),
            ("uploads", _UPLOADS_ROOT_ENV),
            ("outputs", _OUTPUTS_ROOT_ENV),
            ("jobs", _JOBS_ROOT_ENV),
        )
        if _env_path(env) is not None
    }
    legacy_fallback_allowed = data_root_override is None and configured_data_root is None
    projects_root = projects_override or (
        legacy_locations.projects_root
        if legacy_fallback_allowed
        and (legacy_jobs_location or _has_valid_project(legacy_locations.projects_root))
        else data_root / "projects"
    )
    uploads_root = uploads_override or (
        legacy_locations.uploads_root
        if legacy_fallback_allowed and _has_entries(legacy_locations.uploads_root)
        else data_root / "uploads"
    )
    outputs_root = outputs_override or (
        legacy_locations.outputs_root
        if legacy_fallback_allowed and _has_entries(legacy_locations.outputs_root)
        else data_root / "outputs"
    )
    jobs_root = jobs_override or (
        legacy_locations.jobs_root
        if legacy_fallback_allowed and _has_entries(legacy_locations.jobs_root)
        else data_root / "jobs"
    )
    return AppLocations(
        config_root=config_root,
        data_root=data_root,
        state_root=state_root,
        cache_root=cache_root,
        projects_root=projects_root,
        uploads_root=uploads_root,
        outputs_root=outputs_root,
        jobs_root=jobs_root,
        preferences_path=config_root / "preferences.json",
        location_config_path=_location_config_path(config_root),
        legacy_locations=legacy_locations,
        has_legacy_data=_legacy_has_data(legacy_locations),
        overrides=overrides,
    )
