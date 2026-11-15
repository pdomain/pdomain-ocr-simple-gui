"""Safety tests for app-data migration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.locations import AppLocations, LegacyLocations


@pytest.fixture(autouse=True)
def _isolate_committed_location_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(tmp_path / "config"))


def _locations(tmp_path: Path, *, overrides: dict[str, str] | None = None) -> AppLocations:
    old = tmp_path / "old"
    return AppLocations(
        config_root=tmp_path / "config",
        data_root=tmp_path / "current",
        state_root=tmp_path / "state",
        cache_root=tmp_path / "cache",
        projects_root=old / "projects",
        uploads_root=old / "uploads",
        outputs_root=old / "outputs",
        jobs_root=old / "jobs",
        preferences_path=tmp_path / "config" / "preferences.json",
        location_config_path=tmp_path / "config" / "data-location.json",
        legacy_locations=LegacyLocations(old / "projects", old / "uploads", old / "outputs", old / "jobs"),
        has_legacy_data=True,
        overrides=overrides or {},
    )


def _project(
    root: Path,
    project_id: str,
    *,
    source_path: str = "",
    output_dir: str = "",
    status_output_dir: str = "",
) -> None:
    project = root / project_id
    project.mkdir(parents=True)
    (project / "pages").mkdir()
    (project / "pages" / "page-001.txt").write_text("recognized", encoding="utf-8")
    (project / "project.json").write_text(
        json.dumps(
            {
                "spec": {
                    "project_id": project_id,
                    "source_path": source_path,
                    "output_dir": output_dir,
                },
                "status": {"project_id": project_id, "output_dir": status_output_dir},
            }
        ),
        encoding="utf-8",
    )


def _write_metadata(root: Path, project_id: str, mode: str) -> None:
    metadata = root / project_id
    metadata.mkdir(parents=True)
    (metadata / "output_mode.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")


def _prepare_owned_project(tmp_path: Path) -> tuple[AppLocations, Path]:
    locations = _locations(tmp_path)
    project_id = "valid-job"
    upload_id = "upload-1"
    upload = locations.uploads_root / upload_id
    upload.mkdir(parents=True)
    (upload / "scan.png").write_bytes(b"source image")
    mirror = locations.outputs_root / project_id
    mirror.mkdir(parents=True)
    (mirror / "result.txt").write_text("output", encoding="utf-8")
    _write_metadata(locations.jobs_root, project_id, "managed")
    _project(
        locations.projects_root,
        project_id,
        source_path=str(upload),
        output_dir=str(mirror),
        status_output_dir=str(mirror),
    )
    return locations, tmp_path / "new-data"


def test_plan_selects_only_valid_projects_and_retains_custom_root_entries(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import build_migration_plan

    locations = _locations(tmp_path)
    _project(locations.projects_root, "valid-job")
    (locations.projects_root / "unrelated").mkdir()
    (locations.projects_root / "notes.txt").write_text("do not migrate", encoding="utf-8")
    invalid = locations.projects_root / "wrong-id"
    invalid.mkdir()
    (invalid / "project.json").write_text(
        json.dumps({"spec": {"project_id": "other"}, "status": {"project_id": "other"}}),
        encoding="utf-8",
    )
    _project(locations.projects_root, "not.a-project")

    plan = build_migration_plan(locations, tmp_path / "new-data")

    assert plan.project_ids == ("valid-job",)
    assert set(plan.retained_items) == {"unrelated", "notes.txt", "wrong-id", "not.a-project"}


def test_plan_copies_only_referenced_owned_uploads_outputs_and_metadata(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import build_migration_plan

    locations, destination = _prepare_owned_project(tmp_path)
    unrelated_upload = locations.uploads_root / "unrelated-upload"
    unrelated_upload.mkdir()
    (unrelated_upload / "keep.png").write_bytes(b"keep")
    external = tmp_path / "external-output"
    external.mkdir()
    (external / "keep.txt").write_text("keep", encoding="utf-8")
    _project(
        locations.projects_root,
        "external-job",
        source_path=str(unrelated_upload),
        output_dir=str(external),
    )
    _write_metadata(locations.jobs_root, "orphan-job", "managed")

    plan = build_migration_plan(locations, destination)

    assert plan.project_ids == ("external-job", "valid-job")
    assert plan.upload_ids == ("unrelated-upload", "upload-1")
    assert plan.managed_output_ids == ("valid-job",)
    assert plan.metadata_ids == ("valid-job",)


@pytest.mark.parametrize("path_name", ["config_root", "state_root", "cache_root"])
def test_plan_rejects_destination_that_overlaps_non_data_app_roots(tmp_path: Path, path_name: str) -> None:
    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    locations = _locations(tmp_path)
    target = getattr(locations, path_name) / "child"

    with pytest.raises(MigrationBlockedError, match="overlaps"):
        _ = build_migration_plan(locations, target)


def test_plan_blocks_overrides_and_nonempty_or_overlapping_destination(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    with pytest.raises(MigrationBlockedError, match="overrides"):
        _ = build_migration_plan(
            _locations(tmp_path, overrides={"projects": "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"}),
            tmp_path / "new-data",
        )
    locations = _locations(tmp_path)
    locations.projects_root.mkdir(parents=True)
    nonempty = tmp_path / "new-data"
    nonempty.mkdir()
    (nonempty / "owner-file.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(MigrationBlockedError, match="empty"):
        _ = build_migration_plan(locations, nonempty)
    with pytest.raises(MigrationBlockedError, match="overlaps"):
        _ = build_migration_plan(locations, locations.projects_root / "child")


def test_plan_rejects_symlink_ancestor_and_source_descendant(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    locations = _locations(tmp_path)
    locations.projects_root.mkdir(parents=True)
    destination_parent = tmp_path / "destination-parent"
    destination_parent.symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(MigrationBlockedError, match="symlink"):
        _ = build_migration_plan(locations, destination_parent / "new-data")

    destination_parent.unlink()
    (locations.projects_root / "escape").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(MigrationBlockedError, match="symlink"):
        _ = build_migration_plan(locations, tmp_path / "new-data")


def test_execute_copies_rebased_app_owned_data_and_preserves_originals(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import build_migration_plan, execute_migration

    locations, destination = _prepare_owned_project(tmp_path)
    external = tmp_path / "external-output"
    external.mkdir()
    external_file = external / "keep.txt"
    external_file.write_text("external", encoding="utf-8")
    _project(
        locations.projects_root, "external-job", output_dir=str(external), status_output_dir=str(external)
    )
    plan = build_migration_plan(locations, destination)

    result = execute_migration(plan, is_active=lambda: False)

    assert result.data_root == destination
    assert result.project_ids == ("external-job", "valid-job")
    valid_payload = json.loads(
        (destination / "projects" / "valid-job" / "project.json").read_text(encoding="utf-8")
    )
    assert valid_payload["spec"]["source_path"] == str(destination / "uploads" / "upload-1")
    assert valid_payload["spec"]["output_dir"] == str(destination / "outputs" / "valid-job")
    assert valid_payload["status"]["output_dir"] == str(destination / "outputs" / "valid-job")
    assert (destination / "projects" / "valid-job" / "pages" / "page-001.txt").read_text() == "recognized"
    assert (destination / "uploads" / "upload-1" / "scan.png").read_bytes() == b"source image"
    assert (destination / "outputs" / "valid-job" / "result.txt").read_text() == "output"
    assert (destination / "jobs" / "valid-job" / "output_mode.json").exists()
    assert not (destination / "outputs" / "external-job").exists()
    assert external_file.read_text() == "external"
    assert (locations.projects_root / "valid-job" / "project.json").exists()


def test_parent_segments_cannot_hide_destination_overlap(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    locations, _ = _prepare_owned_project(tmp_path)
    (tmp_path / "outside").mkdir()
    destination = tmp_path / "outside" / ".." / "old" / "projects" / "new-data"
    with pytest.raises(MigrationBlockedError, match="overlap"):
        _ = build_migration_plan(locations, destination)


def test_config_override_does_not_block_moving_data(tmp_path: Path) -> None:
    from dataclasses import replace

    from pdomain_ocr_simple_gui.migration import build_migration_plan

    locations, destination = _prepare_owned_project(tmp_path)
    locations = replace(locations, overrides={"config": "PD_OCR_SIMPLE_GUI_CONFIG_ROOT"})
    assert build_migration_plan(locations, destination).destination == destination


@pytest.mark.parametrize("change", ["add", "remove"])
def test_source_directory_changes_block_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from pdomain_ocr_simple_gui import locations as locations_module
    from pdomain_ocr_simple_gui import migration

    locations, destination = _prepare_owned_project(tmp_path)
    empty = locations.projects_root / "valid-job" / "empty-folder"
    if change == "remove":
        empty.mkdir()
    monkeypatch.setattr(locations_module, "_config_root", lambda: locations.config_root)
    original_copy = migration._copy_tree

    def copy_and_change(source: Path, target: Path) -> None:
        original_copy(source, target)
        if source == locations.projects_root / "valid-job":
            if change == "add":
                empty.mkdir()
            else:
                empty.rmdir()

    monkeypatch.setattr(migration, "_copy_tree", copy_and_change)
    with pytest.raises(migration.MigrationBlockedError, match="changed"):
        _ = migration.execute_migration(
            migration.build_migration_plan(locations, destination), is_active=lambda: False
        )
    assert not locations.location_config_path.exists()
    assert (locations.uploads_root / "upload-1" / "scan.png").exists()


def test_execute_rejects_active_work_without_creating_destination(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import (
        MigrationBlockedError,
        build_migration_plan,
        execute_migration,
    )

    locations, destination = _prepare_owned_project(tmp_path)
    plan = build_migration_plan(locations, destination)

    with pytest.raises(MigrationBlockedError, match="active"):
        _ = execute_migration(plan, is_active=lambda: True)

    assert not destination.exists()


def test_execute_removes_staging_after_copy_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pdomain_ocr_simple_gui import migration

    locations, destination = _prepare_owned_project(tmp_path)
    plan = migration.build_migration_plan(locations, destination)
    original_copytree = shutil.copytree

    def fail_after_copy(source: Path, target: Path, *args: object, **kwargs: object) -> Path:
        _ = original_copytree(source, target, *args, **kwargs)
        raise OSError("simulated copy failure")

    monkeypatch.setattr(migration.shutil, "copytree", fail_after_copy)

    with pytest.raises(OSError, match="simulated copy failure"):
        _ = migration.execute_migration(plan, is_active=lambda: False)

    assert not destination.exists()
    assert not list(destination.parent.glob(".new-data.*.staging"))
    assert (locations.projects_root / "valid-job" / "project.json").exists()


def test_execute_rejects_hash_mismatch_and_keeps_originals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui import migration

    locations, destination = _prepare_owned_project(tmp_path)
    plan = migration.build_migration_plan(locations, destination)
    original_copytree = shutil.copytree

    def corrupt_copy(source: Path, target: Path, *args: object, **kwargs: object) -> Path:
        copied = original_copytree(source, target, *args, **kwargs)
        if source.name == "valid-job":
            (target / "pages" / "page-001.txt").write_text("corrupted", encoding="utf-8")
        return copied

    monkeypatch.setattr(migration.shutil, "copytree", corrupt_copy)

    with pytest.raises(migration.MigrationBlockedError, match="verification failed"):
        _ = migration.execute_migration(plan, is_active=lambda: False)

    assert not destination.exists()
    assert (locations.projects_root / "valid-job" / "pages" / "page-001.txt").read_text() == "recognized"


def test_execute_rejects_source_mutation_before_publish(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import (
        MigrationBlockedError,
        build_migration_plan,
        execute_migration,
    )

    locations, destination = _prepare_owned_project(tmp_path)
    plan = build_migration_plan(locations, destination)
    calls = 0

    def activity_gate() -> bool:
        nonlocal calls
        calls += 1
        if calls == 2:
            (locations.projects_root / "valid-job" / "pages" / "page-001.txt").write_text(
                "mutated", encoding="utf-8"
            )
        return False

    with pytest.raises(MigrationBlockedError, match="source changed"):
        _ = execute_migration(plan, is_active=activity_gate)

    assert not destination.exists()


def test_pointer_failure_keeps_original_root_authoritative_and_verified_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui import migration

    locations, destination = _prepare_owned_project(tmp_path)
    plan = migration.build_migration_plan(locations, destination)

    def fail_pointer(_: Path) -> None:
        raise OSError("pointer write failed")

    monkeypatch.setattr(migration, "write_configured_data_root", fail_pointer)

    with pytest.raises(migration.MigrationCommitError, match="pointer write failed") as error:
        _ = migration.execute_migration(plan, is_active=lambda: False)

    assert error.value.recovery_root == destination
    assert (destination / "projects" / "valid-job" / "project.json").exists()
    assert (locations.projects_root / "valid-job" / "project.json").exists()
    assert not locations.location_config_path.exists()


def test_post_commit_preference_snapshot_rebases_only_owned_recent_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui import locations as locations_module
    from pdomain_ocr_simple_gui.migration import build_migration_plan, execute_migration

    locations, destination = _prepare_owned_project(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    payload = {
        "app": {
            "jobs_location": str(locations.projects_root),
            "recent_projects": [
                {
                    "project_id": "valid-job",
                    "source_path": str(locations.uploads_root / "upload-1"),
                    "output_dir": str(locations.outputs_root / "valid-job"),
                },
                {
                    "project_id": "unknown-job",
                    "source_path": str(external),
                    "output_dir": str(external),
                },
            ],
        }
    }
    locations.preferences_path.parent.mkdir(parents=True)
    locations.preferences_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(locations_module, "_config_root", lambda: locations.config_root)

    result = execute_migration(build_migration_plan(locations, destination), is_active=lambda: False)
    updated = json.loads(locations.preferences_path.read_text(encoding="utf-8"))

    assert result.preference_error is None
    assert updated["app"]["jobs_location"] == ""
    assert updated["app"]["recent_projects"][0] == {
        "project_id": "valid-job",
        "source_path": str(destination / "uploads" / "upload-1"),
        "output_dir": str(destination / "outputs" / "valid-job"),
    }
    assert updated["app"]["recent_projects"][1]["source_path"] == str(external)


def test_restart_reads_committed_pointer_and_pref_failure_does_not_undo_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui import locations as locations_module
    from pdomain_ocr_simple_gui.migration import build_migration_plan, execute_migration

    locations, destination = _prepare_owned_project(tmp_path)
    locations.preferences_path.parent.mkdir(parents=True)
    locations.preferences_path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(locations_module, "_config_root", lambda: locations.config_root)
    plan = build_migration_plan(locations, destination)

    result = execute_migration(plan, is_active=lambda: False)
    for name in (
        "PD_OCR_SIMPLE_GUI_CONFIG_ROOT",
        "PD_OCR_SIMPLE_GUI_DATA_ROOT",
        "PD_OCR_SIMPLE_GUI_STATE_ROOT",
        "PD_OCR_SIMPLE_GUI_CACHE_ROOT",
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT",
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT",
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT",
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    restarted = locations_module.get_locations(legacy_jobs_location=str(locations.projects_root))

    assert result.preference_error is not None
    assert restarted.data_root == destination
    assert restarted.projects_root == destination / "projects"
    assert (locations.projects_root / "valid-job" / "project.json").exists()


@pytest.mark.parametrize("suffix", ["saved-data", "child/../saved-data"])
def test_plan_blocks_data_inside_removable_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    import sys

    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    locations = _locations(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(sys, "prefix", str(runtime))
    with pytest.raises(MigrationBlockedError, match=r"outside.*installed"):
        _ = build_migration_plan(locations, runtime / suffix)
    assert not (runtime / "saved-data").exists()


def test_plan_can_move_legacy_data_out_of_the_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from pdomain_ocr_simple_gui.migration import build_migration_plan

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    locations = _locations(runtime)
    _project(locations.projects_root, "legacy-job")
    monkeypatch.setattr(sys, "prefix", str(runtime))
    plan = build_migration_plan(locations, tmp_path / "safe-data")
    assert plan.project_ids == ("legacy-job",)
    assert (locations.projects_root / "legacy-job/project.json").is_file()


def test_malformed_destination_is_a_blocked_plan_without_writes(tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.migration import MigrationBlockedError, build_migration_plan

    locations = _locations(tmp_path)
    with pytest.raises(MigrationBlockedError, match="resolve"):
        _ = build_migration_plan(locations, tmp_path / "bad\0data")
    assert not locations.location_config_path.exists()
    assert not locations.projects_root.exists()
