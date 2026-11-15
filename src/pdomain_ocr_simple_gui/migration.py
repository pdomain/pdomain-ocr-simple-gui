"""Conservative app-data migration planning and execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from filelock import FileLock
from pydantic import TypeAdapter, ValidationError
from typing_extensions import override

from pdomain_ocr_simple_gui.locations import (
    AppLocations,
    LocationConfigError,
    is_within_installation,
    write_configured_data_root,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


_OBJECT_ADAPTER = TypeAdapter(dict[str, object])
_LIST_ADAPTER = TypeAdapter(list[object])
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+")


class MigrationBlockedError(RuntimeError):
    """Raised when migration cannot prove that it is safe to proceed."""


class MigrationCommitError(RuntimeError):
    """Raised when the verified copy exists but the location pointer was not saved."""

    @override
    def __init__(self, recovery_root: Path, cause: Exception) -> None:
        self.recovery_root: Path = recovery_root
        super().__init__(
            f"migration copy retained at {recovery_root}; failed to update location pointer: {cause}"
        )


@dataclass(frozen=True)
class MigrationPlan:
    """Verified migration inputs, destination, and retained source entries."""

    locations: AppLocations
    destination: Path
    project_ids: tuple[str, ...]
    upload_ids: tuple[str, ...]
    managed_output_ids: tuple[str, ...]
    metadata_ids: tuple[str, ...]
    retained_items: tuple[str, ...]


@dataclass(frozen=True)
class MigrationResult:
    """Published data root and any non-authoritative preference follow-up error."""

    data_root: Path
    project_ids: tuple[str, ...]
    preference_error: str | None


@dataclass(frozen=True)
class _FileFingerprint:
    relative_path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class _TreeManifest:
    root: Path
    files: tuple[_FileFingerprint, ...]
    directories: tuple[Path, ...]


@dataclass(frozen=True)
class _CopyEntry:
    source: Path
    target: Path


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _read_object(path: Path) -> dict[str, object]:
    try:
        return _OBJECT_ADAPTER.validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        raise MigrationBlockedError(f"cannot read migration metadata: {path}") from None


def _project_payload(path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    payload = _read_object(path / "project.json")
    try:
        spec = _OBJECT_ADAPTER.validate_python(payload["spec"])
        status = _OBJECT_ADAPTER.validate_python(payload["status"])
    except (KeyError, ValidationError):
        raise MigrationBlockedError(f"invalid project metadata: {path / 'project.json'}") from None
    project_id = path.name
    if spec.get("project_id") != project_id or status.get("project_id") != project_id:
        raise MigrationBlockedError(f"project identifiers do not match directory: {path}")
    return payload, spec, status


def _is_valid_project(path: Path) -> bool:
    if not path.is_dir() or path.is_symlink() or not _IDENTIFIER.fullmatch(path.name):
        return False
    try:
        _ = _project_payload(path)
    except MigrationBlockedError:
        return False
    return True


def _overlaps(left: Path, right: Path) -> bool:
    absolute_left = _absolute(left)
    absolute_right = _absolute(right)
    return (
        absolute_left == absolute_right
        or absolute_left in absolute_right.parents
        or absolute_right in absolute_left.parents
    )


def _has_symlink_ancestor(path: Path) -> bool:
    current = path.expanduser().absolute()
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _tree_has_symlink(root: Path) -> bool:
    if root.is_symlink():
        return True
    if not root.exists() or not root.is_dir():
        return False
    try:
        for directory, names, files in os.walk(root, followlinks=False):
            current = Path(directory)
            if any((current / name).is_symlink() for name in (*names, *files)):
                return True
    except OSError:
        return True
    return False


def _validate_paths(locations: AppLocations, destination: Path) -> Path:
    roots = (
        locations.data_root,
        locations.config_root,
        locations.state_root,
        locations.cache_root,
        locations.projects_root,
        locations.uploads_root,
        locations.outputs_root,
        locations.jobs_root,
    )
    if any(_has_symlink_ancestor(path) or _tree_has_symlink(path) for path in (*roots, destination)):
        raise MigrationBlockedError("symlinked migration paths are not supported")
    destination = _absolute(destination)
    if is_within_installation(destination):
        raise MigrationBlockedError("Choose a data folder outside the installed application")
    if any(_overlaps(destination, path) for path in roots):
        raise MigrationBlockedError("destination overlaps an existing app path")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise MigrationBlockedError("destination must be an empty directory")
    return destination


def _owned_upload_id(source_path: object, uploads_root: Path) -> str | None:
    if not isinstance(source_path, str):
        return None
    candidate = _absolute(Path(source_path))
    if (
        candidate.parent != _absolute(uploads_root)
        or not _IDENTIFIER.fullmatch(candidate.name)
        or not candidate.is_dir()
    ):
        return None
    return candidate.name


def _has_managed_mirror(output_path: object, outputs_root: Path, project_id: str, mode: str | None) -> bool:
    if mode != "managed" or not isinstance(output_path, str):
        return False
    expected = _absolute(outputs_root / project_id)
    provided = _absolute(Path(output_path))
    return provided == expected and not _has_symlink_ancestor(expected)


def _metadata_mode(metadata_file: Path) -> str | None:
    if not metadata_file.is_file():
        return None
    try:
        mode = _read_object(metadata_file).get("mode")
    except MigrationBlockedError:
        return None
    return mode if isinstance(mode, str) else None


def build_migration_plan(locations: AppLocations, destination: Path) -> MigrationPlan:
    """Validate a requested destination and identify only owned data to copy."""
    if set(locations.overrides).intersection({"data", "projects", "uploads", "outputs", "jobs"}):
        raise MigrationBlockedError("environment root overrides must be removed before migration")
    try:
        destination = _validate_paths(locations, destination)
    except ValueError as exc:
        raise MigrationBlockedError("Cannot resolve the requested data folder") from exc
    projects: list[str] = []
    retained: list[str] = []
    if locations.projects_root.is_dir():
        try:
            children = sorted(locations.projects_root.iterdir())
        except OSError:
            raise MigrationBlockedError(f"cannot inspect projects root: {locations.projects_root}") from None
        for child in children:
            if _is_valid_project(child):
                projects.append(child.name)
            else:
                retained.append(child.name)

    upload_ids: set[str] = set()
    managed_outputs: list[str] = []
    metadata_ids: list[str] = []
    for project_id in projects:
        _, spec, _ = _project_payload(locations.projects_root / project_id)
        upload_id = _owned_upload_id(spec.get("source_path"), locations.uploads_root)
        if upload_id is not None:
            upload_ids.add(upload_id)
        metadata_root = locations.jobs_root / project_id
        if metadata_root.is_dir():
            metadata_ids.append(project_id)
        mode = _metadata_mode(metadata_root / "output_mode.json")
        if _has_managed_mirror(spec.get("output_dir"), locations.outputs_root, project_id, mode):
            managed_outputs.append(project_id)

    return MigrationPlan(
        locations=locations,
        destination=destination,
        project_ids=tuple(projects),
        upload_ids=tuple(sorted(upload_ids)),
        managed_output_ids=tuple(managed_outputs),
        metadata_ids=tuple(metadata_ids),
        retained_items=tuple(retained),
    )


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(root: Path) -> _TreeManifest:
    if not root.is_dir() or root.is_symlink():
        raise MigrationBlockedError(f"migration source is not a regular directory: {root}")
    files: list[_FileFingerprint] = []
    directory_paths: list[Path] = []
    try:
        for directory, directories, names in os.walk(root, followlinks=False):
            current = Path(directory)
            directories.sort()
            directory_paths.append(current.relative_to(root))
            if any((current / name).is_symlink() for name in (*directories, *names)):
                raise MigrationBlockedError(f"symlink found in migration source: {root}")
            for name in sorted(names):
                path = current / name
                if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                    raise MigrationBlockedError(f"non-regular file in migration source: {path}")
                files.append(_FileFingerprint(path.relative_to(root), path.stat().st_size, _hash(path)))
    except OSError:
        raise MigrationBlockedError(f"cannot read migration source: {root}") from None
    return _TreeManifest(
        root=root,
        files=tuple(sorted(files, key=lambda item: item.relative_path.as_posix())),
        directories=tuple(sorted(directory_paths, key=lambda item: item.as_posix())),
    )


def _verify_manifest(manifest: _TreeManifest, *, message: str) -> None:
    try:
        current = _manifest(manifest.root)
    except MigrationBlockedError as exc:
        raise MigrationBlockedError(f"{message}: {manifest.root}") from exc
    if current.files != manifest.files or current.directories != manifest.directories:
        raise MigrationBlockedError(f"{message}: {manifest.root}")


def _copy_tree(source: Path, target: Path) -> None:
    _ = shutil.copytree(source, target)


def _copy_entries(entries: Iterable[_CopyEntry]) -> tuple[_TreeManifest, ...]:
    target_manifests: list[_TreeManifest] = []
    for entry in entries:
        source_manifest = _manifest(entry.source)
        _copy_tree(entry.source, entry.target)
        target_manifest = _manifest(entry.target)
        if (
            target_manifest.files != source_manifest.files
            or target_manifest.directories != source_manifest.directories
        ):
            raise MigrationBlockedError(f"verification failed for {entry.source}")
        target_manifests.append(target_manifest)
    return tuple(target_manifests)


def _project_upload_id(plan: MigrationPlan, source_path: object) -> str | None:
    upload_id = _owned_upload_id(source_path, plan.locations.uploads_root)
    return upload_id if upload_id in plan.upload_ids else None


def _rebase_projects(plan: MigrationPlan, staging: Path) -> None:
    for project_id in plan.project_ids:
        project = staging / "projects" / project_id
        payload, spec, status = _project_payload(project)
        upload_id = _project_upload_id(plan, spec.get("source_path"))
        if upload_id is not None:
            spec["source_path"] = str(plan.destination / "uploads" / upload_id)
        if project_id in plan.managed_output_ids:
            expected = _absolute(plan.locations.outputs_root / project_id)
            if _absolute(Path(str(spec.get("output_dir", "")))) == expected:
                spec["output_dir"] = str(plan.destination / "outputs" / project_id)
            if _absolute(Path(str(status.get("output_dir", "")))) == expected:
                status["output_dir"] = str(plan.destination / "outputs" / project_id)
        payload["spec"] = spec
        payload["status"] = status
        _ = (project / "project.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _ = _project_payload(project)


def _source_entries(plan: MigrationPlan, staging: Path) -> tuple[_CopyEntry, ...]:
    entries: list[_CopyEntry] = [
        _CopyEntry(plan.locations.projects_root / project_id, staging / "projects" / project_id)
        for project_id in plan.project_ids
    ]
    entries.extend(
        _CopyEntry(plan.locations.uploads_root / upload_id, staging / "uploads" / upload_id)
        for upload_id in plan.upload_ids
    )
    entries.extend(
        _CopyEntry(plan.locations.outputs_root / project_id, staging / "outputs" / project_id)
        for project_id in plan.managed_output_ids
        if (plan.locations.outputs_root / project_id).is_dir()
    )
    entries.extend(
        _CopyEntry(plan.locations.jobs_root / project_id, staging / "jobs" / project_id)
        for project_id in plan.metadata_ids
    )
    return tuple(entries)


def _same_plan(left: MigrationPlan, right: MigrationPlan) -> bool:
    return (
        left.destination == right.destination
        and left.project_ids == right.project_ids
        and left.upload_ids == right.upload_ids
        and left.managed_output_ids == right.managed_output_ids
        and left.metadata_ids == right.metadata_ids
    )


def _update_preferences(plan: MigrationPlan) -> str | None:
    path = plan.locations.preferences_path
    if not path.exists():
        return None
    lock = FileLock(str(path.with_suffix(".lock")))
    try:
        with lock:
            payload = _read_object(path)
            app = _OBJECT_ADAPTER.validate_python(payload["app"])
            changed = False
            jobs_location = app.get("jobs_location")
            if isinstance(jobs_location, str) and _absolute(Path(jobs_location)) == _absolute(
                plan.locations.projects_root
            ):
                app["jobs_location"] = ""
                changed = True
            recent: object = app.get("recent_projects")
            try:
                recent_entries = _LIST_ADAPTER.validate_python(recent)
            except ValidationError:
                recent_entries = []
            if recent_entries:
                rebased_recent: list[object] = []
                for entry in recent_entries:
                    try:
                        updated = _OBJECT_ADAPTER.validate_python(entry)
                    except ValidationError:
                        rebased_recent.append(entry)
                        continue
                    project_id = updated.get("project_id")
                    if isinstance(project_id, str) and project_id in plan.project_ids:
                        upload_id = _project_upload_id(plan, updated.get("source_path"))
                        if upload_id is not None:
                            updated["source_path"] = str(plan.destination / "uploads" / upload_id)
                        if project_id in plan.managed_output_ids and _has_managed_mirror(
                            updated.get("output_dir"), plan.locations.outputs_root, project_id, "managed"
                        ):
                            updated["output_dir"] = str(plan.destination / "outputs" / project_id)
                    rebased_recent.append(updated)
                if rebased_recent != recent:
                    app["recent_projects"] = rebased_recent
                    changed = True
            if not changed:
                return None
            payload["app"] = app
            staged = path.parent / f".{path.name}.{uuid4().hex}.tmp"
            try:
                _ = staged.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                os.replace(staged, path)
            finally:
                staged.unlink(missing_ok=True)
    except (KeyError, OSError, ValidationError, MigrationBlockedError) as exc:
        return f"app preferences were not updated after migration: {exc}"
    return None


def execute_migration(plan: MigrationPlan, *, is_active: Callable[[], bool]) -> MigrationResult:
    """Copy verified app-owned files, publish them, then atomically save the data pointer."""
    if is_active():
        raise MigrationBlockedError("active work blocks migration")
    current_plan = build_migration_plan(plan.locations, plan.destination)
    if not _same_plan(plan, current_plan):
        raise MigrationBlockedError("migration sources changed since planning")
    plan.destination.parent.mkdir(parents=True, exist_ok=True)
    staging = plan.destination.parent / f".{plan.destination.name}.{uuid4().hex}.staging"
    entries = _source_entries(plan, staging)
    try:
        source_manifests = tuple(_manifest(entry.source) for entry in entries)
        _ = _copy_entries(entries)
        _rebase_projects(plan, staging)
        publish_manifests = tuple(_manifest(entry.target) for entry in entries)
        if is_active():
            raise MigrationBlockedError("active work began during migration")
        for manifest in source_manifests:
            _verify_manifest(manifest, message="source changed during migration")
        for manifest in publish_manifests:
            _verify_manifest(manifest, message="verification failed")
        _ = staging.replace(plan.destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    try:
        write_configured_data_root(plan.destination)
    except (LocationConfigError, OSError) as exc:
        raise MigrationCommitError(plan.destination, exc) from exc
    return MigrationResult(
        data_root=plan.destination,
        project_ids=plan.project_ids,
        preference_error=_update_preferences(plan),
    )
