"""Tests for app-owned location resolution."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_legacy_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pdomain_ocr_simple_gui import locations

    legacy_root = tmp_path / "legacy"
    monkeypatch.setattr(
        locations,
        "_legacy_default_locations",
        lambda: locations.LegacyLocations(
            projects_root=legacy_root / "projects",
            uploads_root=legacy_root / "uploads",
            outputs_root=legacy_root / "outputs",
            jobs_root=legacy_root / "jobs",
        ),
    )


def _clear_location_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_locations_uses_platform_defaults_without_creating_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui import locations

    _clear_location_overrides(monkeypatch)
    config_root = tmp_path / "config"
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    cache_root = tmp_path / "cache"
    monkeypatch.setattr(locations.platformdirs, "user_config_path", lambda *_args, **_kwargs: config_root)
    monkeypatch.setattr(locations.platformdirs, "user_data_path", lambda *_args, **_kwargs: data_root)
    monkeypatch.setattr(locations.platformdirs, "user_state_path", lambda *_args, **_kwargs: state_root)
    monkeypatch.setattr(locations.platformdirs, "user_cache_path", lambda *_args, **_kwargs: cache_root)

    effective = locations.get_locations(legacy_jobs_location="")

    assert effective.config_root == config_root
    assert effective.data_root == data_root
    assert effective.state_root == state_root
    assert effective.cache_root == cache_root
    assert effective.projects_root == data_root / "projects"
    assert effective.uploads_root == data_root / "uploads"
    assert effective.outputs_root == data_root / "outputs"
    assert effective.jobs_root == data_root / "jobs"
    assert not config_root.exists()
    assert not data_root.exists()


def test_child_environment_overrides_beat_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui.locations import get_locations

    _clear_location_overrides(monkeypatch)
    data_root = tmp_path / "data"
    projects_root = tmp_path / "projects-override"
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_DATA_ROOT", str(data_root))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))

    effective = get_locations(legacy_jobs_location="")

    assert effective.projects_root == projects_root
    assert effective.uploads_root == data_root / "uploads"
    assert effective.outputs_root == data_root / "outputs"
    assert effective.jobs_root == data_root / "jobs"
    assert effective.overrides["projects"] == "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"


def test_legacy_jobs_location_remains_effective_until_migration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui.locations import get_locations

    _clear_location_overrides(monkeypatch)
    legacy_projects = tmp_path / "old-custom-projects"
    project = legacy_projects / "legacy-project"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(tmp_path / "config"))

    effective = get_locations(legacy_jobs_location=str(legacy_projects))

    assert effective.projects_root == legacy_projects
    assert effective.has_legacy_data
    assert effective.legacy_locations.projects_root == legacy_projects


def test_empty_legacy_root_does_not_replace_new_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui.locations import get_locations

    _clear_location_overrides(monkeypatch)
    data_root = tmp_path / "new-data"
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_DATA_ROOT", str(data_root))

    effective = get_locations()

    assert effective.projects_root == data_root / "projects"
    assert not effective.has_legacy_data


def test_write_configured_data_root_switches_future_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui.locations import get_locations, write_configured_data_root

    _clear_location_overrides(monkeypatch)
    config_root = tmp_path / "config"
    data_root = tmp_path / "chosen-data"
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config_root))

    write_configured_data_root(data_root)

    assert get_locations(legacy_jobs_location="").data_root == data_root
    assert (config_root / "data-location.json").read_text(encoding="utf-8") == (
        '{\n  "data_root": "' + str(data_root) + '"\n}'
    )


def test_configured_data_root_beats_legacy_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui import locations

    _clear_location_overrides(monkeypatch)
    config_root = tmp_path / "config"
    configured_root = tmp_path / "configured-data"
    legacy_root = tmp_path / "legacy"
    project = legacy_root / "projects" / "legacy-project"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config_root))
    monkeypatch.setattr(
        locations,
        "_legacy_default_locations",
        lambda: locations.LegacyLocations(
            projects_root=legacy_root / "projects",
            uploads_root=legacy_root / "uploads",
            outputs_root=legacy_root / "outputs",
            jobs_root=legacy_root / "jobs",
        ),
    )

    locations.write_configured_data_root(configured_root)
    effective = locations.get_locations(legacy_jobs_location=str(legacy_root / "projects"))

    assert effective.projects_root == configured_root / "projects"
    assert effective.legacy_locations.projects_root == legacy_root / "projects"
    assert effective.has_legacy_data


def test_malformed_location_config_is_not_treated_as_empty_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui.locations import LocationConfigError, get_locations

    _clear_location_overrides(monkeypatch)
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "data-location.json").write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config_root))

    with pytest.raises(LocationConfigError):
        _ = get_locations(legacy_jobs_location="")


def test_malformed_app_preferences_are_not_ignored_for_location_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdomain_ocr_simple_gui.locations import LocationConfigError, get_locations

    _clear_location_overrides(monkeypatch)
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "preferences.json").write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config_root))

    with pytest.raises(LocationConfigError):
        _ = get_locations()


def test_existing_root_helpers_follow_data_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from pdomain_ocr_simple_gui import storage
    from pdomain_ocr_simple_gui.routes import jobs, uploads

    _clear_location_overrides(monkeypatch)
    data_root = tmp_path / "app-data"
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_DATA_ROOT", str(data_root))

    assert storage._projects_root() == data_root / "projects"
    assert uploads._upload_root() == data_root / "uploads"
    assert jobs._managed_output_root() == data_root / "outputs"
    assert jobs._jobs_meta_root() == data_root / "jobs"


@pytest.mark.parametrize("suffix", ["", "data", "one/../data"])
def test_installation_guard_protects_runtime_and_descendants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    import sys

    from pdomain_ocr_simple_gui.locations import is_within_installation

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(sys, "prefix", str(runtime))
    assert is_within_installation(runtime / suffix)
    assert not is_within_installation(runtime.parent)
    assert not is_within_installation(tmp_path / "outside")


def test_installation_guard_follows_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from pdomain_ocr_simple_gui.locations import is_within_installation

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(runtime, target_is_directory=True)
    monkeypatch.setattr(sys, "prefix", str(runtime))
    assert is_within_installation(alias / "jobs")
    assert is_within_installation(tmp_path / "outside/../runtime/models")


@pytest.mark.parametrize("bundle", ["OCR Simple GUI.app", "Uninstall OCR Simple GUI.app"])
def test_installation_guard_protects_recursively_removed_macos_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundle: str
) -> None:
    import sys

    from pdomain_ocr_simple_gui.locations import is_within_installation

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "runtime"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    target = tmp_path / "home/Applications" / bundle
    assert is_within_installation(target / "saved-scans")
    assert not is_within_installation(target.parent)


def test_new_configured_data_root_cannot_enter_the_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from pdomain_ocr_simple_gui.locations import LocationConfigError, write_configured_data_root

    runtime = tmp_path / "runtime"
    config = tmp_path / "config"
    monkeypatch.setattr(sys, "prefix", str(runtime))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config))
    with pytest.raises(LocationConfigError, match=r"outside.*installed"):
        write_configured_data_root(runtime / "new-data")
    assert not config.exists()


def test_existing_configured_runtime_data_can_still_be_read_for_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import sys

    from pdomain_ocr_simple_gui.locations import get_locations

    _clear_location_overrides(monkeypatch)
    runtime = tmp_path / "runtime"
    config = tmp_path / "config"
    config.mkdir()
    legacy = runtime / "legacy-data"
    _ = (config / "data-location.json").write_text(json.dumps({"data_root": str(legacy)}))
    monkeypatch.setattr(sys, "prefix", str(runtime))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config))
    assert get_locations(legacy_jobs_location="").data_root == legacy


def test_global_shared_python_prefix_is_not_wholly_app_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from pdomain_ocr_simple_gui.locations import is_within_installation

    global_python = tmp_path / "shared-python"
    monkeypatch.setattr(sys, "prefix", str(global_python))
    monkeypatch.setattr(sys, "base_prefix", str(global_python))
    assert not is_within_installation(global_python / "shared-workspace")


def test_malformed_new_data_root_does_not_create_location_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui.locations import LocationConfigError, write_configured_data_root

    config = tmp_path / "config"
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_CONFIG_ROOT", str(config))
    with pytest.raises(LocationConfigError, match="resolve"):
        write_configured_data_root(tmp_path / "bad\0data")
    assert not config.exists()


def test_installation_guard_rejects_nul_before_platform_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui.locations import is_within_installation

    resolved: list[Path] = []

    def tolerant_resolve(path: Path, strict: bool = False) -> Path:
        del strict
        resolved.append(path)
        return path

    monkeypatch.setattr(Path, "resolve", tolerant_resolve)
    with pytest.raises(ValueError, match="NUL"):
        _ = is_within_installation(tmp_path / "invalid\0folder")
    assert resolved == []
