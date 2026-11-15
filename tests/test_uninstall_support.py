"""Safety boundaries for native uninstall preparation and suite cleanup."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from pdomain_ocr_simple_gui import uninstall_support
from pdomain_ocr_simple_gui.instance import InstanceReply, InstanceStore, new_instance_record


def _environment(root: Path, name: str, *, suite_owner: bool = False) -> Path:
    """Create a minimal uv tool environment inventory."""
    environment = root / name
    site_packages = environment / "Lib" / "site-packages"
    dist_info = site_packages / f"{name}-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("home = test\n", encoding="utf-8")
    record = "pdomain_suite/pdomain-suite.json,,\n" if suite_owner else "other.py,,\n"
    (dist_info / "RECORD").write_text(record, encoding="utf-8")
    return environment


def _plan(suite_root: Path, tools_root: Path, own_environment: Path) -> uninstall_support.CleanupPlan:
    return uninstall_support.plan_suite_cleanup(
        suite_root=suite_root,
        tools_root=tools_root,
        own_environment=own_environment,
    )


def _retained_guard_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SimpleNamespace, Path, Mock, Mock, Mock]:
    from pdomain_ops.suite import paths as suite_paths
    from pdomain_ops.suite import registry as suite_registry

    import pdomain_ocr_simple_gui.locations as locations_module

    installation = tmp_path / "installation"
    installation.mkdir()
    values = {
        name: tmp_path / "retained" / name
        for name in (
            "config_root",
            "data_root",
            "state_root",
            "cache_root",
            "projects_root",
            "uploads_root",
            "outputs_root",
            "jobs_root",
        )
    }
    for root in values.values():
        root.mkdir(parents=True)
        _ = (root / "keep.txt").write_bytes(b"retained data")
    locations = SimpleNamespace(**values, overrides={})
    monkeypatch.setattr(locations_module, "get_locations", lambda: locations)
    monkeypatch.setattr(
        locations_module,
        "sys",
        SimpleNamespace(
            prefix=str(installation), base_prefix=str(tmp_path / "base python"), platform="linux"
        ),
        raising=False,
    )
    for variable in (
        "DOCTR_CACHE_DIR",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "HF_HOME",
        "TORCH_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    stopped = Mock()
    unregistered = Mock()
    base = Mock(return_value=Path(sys.executable))
    monkeypatch.setattr(uninstall_support, "_base_python", base)
    monkeypatch.setattr(uninstall_support, "_stop_verified_instance", stopped)
    monkeypatch.setattr(suite_registry.LocalTomlSuiteRegistry, "unregister", unregistered)
    monkeypatch.setattr(suite_paths, "installed_toml_path", lambda: tmp_path / "suite/installed.toml")
    return locations, installation, stopped, unregistered, base


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        str(path): path.read_bytes() for path in root.rglob("*") if path.is_file() and not path.is_symlink()
    }


@pytest.mark.parametrize(
    "kind",
    [
        "config_root",
        "data_root",
        "state_root",
        "cache_root",
        "projects_root",
        "uploads_root",
        "outputs_root",
        "jobs_root",
        "DOCTR_CACHE_DIR",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "HF_HOME",
        "TORCH_HOME",
        "default_doctr",
        "default_huggingface",
        "default_torch",
        "saved_root",
        "saved_doctr",
        "saved_huggingface",
        "saved_torch",
    ],
)
def test_prepare_refuses_retained_data_inside_installation_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    locations, installation, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    unsafe = installation / "valuable files"
    unsafe.mkdir()
    _ = (unsafe / "keep.txt").write_bytes(b"must survive")
    if kind.endswith("_root") and not kind.startswith("saved"):
        setattr(locations, kind, unsafe)
    elif kind.isupper():
        monkeypatch.setenv(kind, str(unsafe))
    elif kind.startswith("default_"):
        monkeypatch.setenv("HOME", str(installation))
        for variable in ("DOCTR_CACHE_DIR", "HF_HUB_CACHE", "TORCH_HOME"):
            monkeypatch.setenv(variable, str(tmp_path / "safe models" / variable))
        variable = {
            "default_doctr": "DOCTR_CACHE_DIR",
            "default_huggingface": "HF_HUB_CACHE",
            "default_torch": "TORCH_HOME",
        }[kind]
        monkeypatch.delenv(variable)
    else:
        saved = unsafe if kind == "saved_root" else tmp_path / "saved models"
        if kind != "saved_root":
            child = {
                "saved_doctr": "doctr",
                "saved_huggingface": "huggingface/hub",
                "saved_torch": "torch/hub",
            }[kind]
            alias = saved / child
            alias.parent.mkdir(parents=True, exist_ok=True)
            alias.symlink_to(unsafe, target_is_directory=True)
        _ = (locations.config_root / "preferences.json").write_text(
            json.dumps({"app": {"model_cache_location": str(saved)}})
        )
    before = _snapshot_files(tmp_path)

    with pytest.raises(uninstall_support.UninstallPreparationError, match="moved first"):
        _ = uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    assert _snapshot_files(tmp_path) == before
    assert not (locations.state_root / "uninstall-in-progress.json").exists()


def test_prepare_does_not_create_missing_preferences_or_change_cache_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ocr_simple_gui.cache_configuration import startup_state

    locations, _, stopped, unregistered, _ = _retained_guard_setup(tmp_path, monkeypatch)
    cache_before = startup_state.location
    environment_before = dict(uninstall_support.os.environ)

    result = uninstall_support.prepare_uninstall(tmp_path / "tools")

    assert result["prepared"] is True
    stopped.assert_called_once()
    unregistered.assert_called_once()
    assert not (locations.config_root / "preferences.json").exists()
    assert startup_state.location == cache_before
    assert dict(uninstall_support.os.environ) == environment_before


@pytest.mark.parametrize("content", ['{"app":', '{"app": {"model_cache_location": 42}}'])
def test_unreadable_saved_cache_choice_refuses_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    locations, _, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    _ = (locations.config_root / "preferences.json").write_text(content)
    before = _snapshot_files(tmp_path)

    with pytest.raises(uninstall_support.UninstallPreparationError, match="preference"):
        _ = uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    assert _snapshot_files(tmp_path) == before


@pytest.mark.parametrize("source", ["explicit_override", "platform_default", "canonical_registry"])
def test_prepare_refuses_shared_suite_data_inside_installation_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    import platformdirs
    from pdomain_ops.suite import paths as suite_paths

    _, installation, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    suite = installation / "shared suite"
    suite.mkdir()
    _ = (suite / "installed.toml").write_text('[apps.other]\napp_id = "other"\n')
    _ = (suite / "ui-prefs.json").write_text('{"shared": "keep"}')
    _ = (suite / "other-app-data").write_bytes(b"shared data must survive")
    if source == "explicit_override":
        monkeypatch.setenv("PD_SUITE_DATA_DIR", str(suite))
    elif source == "platform_default":
        monkeypatch.delenv("PD_SUITE_DATA_DIR", raising=False)
        monkeypatch.setattr(platformdirs, "user_data_dir", lambda *_args, **_kwargs: str(suite))
    else:
        monkeypatch.setattr(suite_paths, "installed_toml_path", lambda: suite / "installed.toml")
    canonical_getter = Mock(wraps=suite_paths.installed_toml_path)
    monkeypatch.setattr(suite_paths, "installed_toml_path", canonical_getter)
    before = _snapshot_files(tmp_path)

    with pytest.raises(uninstall_support.UninstallPreparationError, match="moved first"):
        _ = uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    if source != "canonical_registry":
        canonical_getter.assert_not_called()
    assert _snapshot_files(tmp_path) == before


def _staged_cleanup(
    tmp_path: Path, *, keep_environment: bool = False, reason: str = "other_registered"
) -> tuple[Path, Path, Path, Path, Path]:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    registry = '[apps.other]\napp_id = "other"\n' if reason == "other_registered" else "[apps]\n"
    _ = (suite_root / "installed.toml").write_text(registry)
    _ = (suite_root / "ui-prefs.json").write_text('{"shared": "keep"}')
    _ = (suite_root / "unknown-user-data").write_bytes(b"user data must stay")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, uninstall_support.APP_ID)
    if reason == "other_installed":
        _ = _environment(tools_root, "other", suite_owner=True)
    elif reason == "unknown_tool_file":
        _ = (tools_root / "unknown-file").write_bytes(b"keep")
    elif reason == "uncertain_tool_inventory":
        (tools_root / "unknown-environment").mkdir()
    elif reason == "malformed_registry":
        _ = (suite_root / "installed.toml").write_text("not valid toml\n")
    staged_script = tmp_path / "uninstall-finalize.py"
    _ = shutil.copyfile(uninstall_support.__file__, staged_script)
    marker = tmp_path / "uninstall-in-progress.json"
    token = "a" * 32
    _ = marker.write_text(
        json.dumps(
            {"app_id": uninstall_support.APP_ID, "operation_token": token, "schema_version": 1},
            sort_keys=True,
        )
    )
    plan = replace(
        _plan(suite_root, tools_root, own_environment),
        finalize_script=str(staged_script),
        uninstall_marker=str(marker),
        operation_token=token,
    )
    plan_path = tmp_path / "uninstall-plan.json"
    _ = plan_path.write_text(
        "\n".join(
            base64.b64encode(value.encode()).decode() or "-"
            for value in (
                plan.suite_root,
                plan.tools_root,
                plan.own_environment,
                plan.reason,
                plan.finalize_script,
                plan.uninstall_marker,
                plan.operation_token,
            )
        )
    )
    if not keep_environment:
        shutil.rmtree(own_environment)
    return staged_script, plan_path, marker, suite_root, own_environment


@pytest.mark.parametrize(
    "reason",
    [
        "other_registered",
        "other_installed",
        "unknown_tool_file",
        "uncertain_tool_inventory",
        "malformed_registry",
        "unknown_suite_file",
    ],
)
def test_finalizer_clears_owned_marker_when_shared_cleanup_is_retained(tmp_path: Path, reason: str) -> None:
    script, plan_path, marker, suite, _ = _staged_cleanup(tmp_path, reason=reason)
    retained = {path: path.read_bytes() for path in suite.iterdir()}

    result = subprocess.run(
        [sys.executable, "-I", str(script), "--execute-plan", str(plan_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert not script.exists()
    assert not plan_path.exists()
    assert (suite / "unknown-user-data").read_bytes() == b"user data must stay"
    if reason != "unknown_suite_file":
        assert {path: path.read_bytes() for path in suite.iterdir()} == retained
    parsed = json.loads(result.stdout)
    assert parsed["suite_cleanup"]["uninstall_marker"] == str(marker)
    assert parsed["suite_cleanup"]["operation_token"] == "a" * 32
    assert parsed["suite_cleanup"]["finalize_script"] == str(script)


def test_finalizer_preserves_a_foreign_operation_marker(tmp_path: Path) -> None:
    script, plan_path, marker, suite, _ = _staged_cleanup(tmp_path)
    foreign_marker = json.dumps(
        {"app_id": uninstall_support.APP_ID, "operation_token": "b" * 32, "schema_version": 1}, sort_keys=True
    )
    _ = marker.write_text(foreign_marker)

    result = subprocess.run(
        [sys.executable, "-I", str(script), "--execute-plan", str(plan_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text() == foreign_marker
    assert (suite / "unknown-user-data").read_bytes() == b"user data must stay"


def test_finalizer_fails_and_preserves_recovery_files_if_tool_remains(tmp_path: Path) -> None:
    script, plan_path, marker, suite, own_environment = _staged_cleanup(tmp_path, keep_environment=True)
    retained = {path: path.read_bytes() for path in suite.iterdir()}
    pending_marker = marker.read_bytes()

    result = subprocess.run(
        [sys.executable, "-I", str(script), "--execute-plan", str(plan_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "environment" in result.stderr.lower()
    assert script.is_file()
    assert plan_path.is_file()
    assert marker.read_bytes() == pending_marker
    assert own_environment.is_dir()
    assert {path: path.read_bytes() for path in suite.iterdir()} == retained


def test_finalizer_rejects_dangling_own_entry_without_touching_foreign_data(tmp_path: Path) -> None:
    script, plan_path, marker, suite, own_environment = _staged_cleanup(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    retained_foreign = foreign / "important.txt"
    _ = retained_foreign.write_bytes(b"keep foreign data")
    own_environment.symlink_to(foreign / "missing-environment", target_is_directory=True)
    retained_suite = {path: path.read_bytes() for path in suite.iterdir()}
    pending_marker = marker.read_bytes()

    result = subprocess.run(
        [sys.executable, "-I", str(script), "--execute-plan", str(plan_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert "environment" in result.stderr.lower()
    assert own_environment.is_symlink()
    assert script.is_file()
    assert plan_path.is_file()
    assert marker.read_bytes() == pending_marker
    assert {path: path.read_bytes() for path in suite.iterdir()} == retained_suite
    assert retained_foreign.read_bytes() == b"keep foreign data"
    assert not (foreign / "missing-environment").exists()


def test_finalizer_keeps_recovery_files_when_own_entry_cannot_be_inspected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script, plan_path, marker, suite, own_environment = _staged_cleanup(tmp_path)
    retained_suite = {path: path.read_bytes() for path in suite.iterdir()}
    pending_marker = marker.read_bytes()
    original_lstat = Path.lstat

    def unreadable(path: Path) -> object:
        if path == own_environment:
            raise PermissionError("inventory denied")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", unreadable)

    result = uninstall_support.main(["--execute-plan", str(plan_path), "--json"])

    assert result != 0
    assert "inventory denied" in capsys.readouterr().err
    assert script.is_file()
    assert plan_path.is_file()
    assert marker.read_bytes() == pending_marker
    assert {path: path.read_bytes() for path in suite.iterdir()} == retained_suite


def test_uncertain_inventory_keeps_shared_integration_files(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    installed = suite_root / "installed.toml"
    prefs = suite_root / "ui-prefs.json"
    installed.write_text("[apps]\n", encoding="utf-8")
    prefs.write_text("{}", encoding="utf-8")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")
    (tools_root / "unknown").mkdir()

    plan = _plan(suite_root, tools_root, own_environment)

    assert plan.safe_to_execute is False
    assert plan.reason == "uncertain_tool_inventory"
    assert plan.actions == ()


def test_installed_but_unregistered_other_app_blocks_suite_cleanup(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    (suite_root / "installed.toml").write_text("[apps]\n", encoding="utf-8")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")
    _ = _environment(tools_root, "other-suite-app", suite_owner=True)

    plan = _plan(suite_root, tools_root, own_environment)

    assert plan.safe_to_execute is False
    assert plan.reason == "other_suite_app_installed"


def test_last_app_removes_only_known_files_and_preserves_unknown_files(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    (suite_root / "installed.toml").write_text("[apps]\n", encoding="utf-8")
    (suite_root / "ui-prefs.json").write_text("{}", encoding="utf-8")
    unknown = suite_root / "legacy-backup.zip"
    unknown.write_text("keep", encoding="utf-8")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")

    plan = _plan(suite_root, tools_root, own_environment)

    assert plan.safe_to_execute is True
    assert [action.kind for action in plan.actions] == ["delete_file", "delete_file", "remove_empty_dir"]
    shutil.rmtree(own_environment)
    uninstall_support.execute_cleanup_plan(plan)
    assert not (suite_root / "installed.toml").exists()
    assert not (suite_root / "ui-prefs.json").exists()
    assert unknown.read_text(encoding="utf-8") == "keep"
    assert suite_root.exists()


def test_finalizer_rechecks_inventory_before_deleting_files(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    installed = suite_root / "installed.toml"
    installed.write_text("[apps]\n", encoding="utf-8")
    prefs = suite_root / "ui-prefs.json"
    prefs.write_text("{}", encoding="utf-8")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")
    plan = _plan(suite_root, tools_root, own_environment)
    _ = _environment(tools_root, "new-suite-app", suite_owner=True)

    outcome = uninstall_support.execute_cleanup_plan(plan)

    assert outcome.safe_to_execute is False
    assert installed.exists()
    assert prefs.exists()


def test_execute_plan_file_returns_json_safe_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")
    plan_path = tmp_path / "plan.json"
    plan = _plan(suite_root, tools_root, own_environment)
    plan_path.write_text(
        "\n".join(
            base64.b64encode(value.encode("utf-8")).decode("ascii") or "-"
            for value in (
                plan.suite_root,
                plan.tools_root,
                plan.own_environment,
                plan.reason,
                plan.finalize_script,
                plan.uninstall_marker,
                plan.operation_token,
            )
        ),
        encoding="ascii",
    )
    shutil.rmtree(own_environment)

    exit_code = uninstall_support.main(["--execute-plan", str(plan_path), "--json"])

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert result["suite_cleanup"]["safe_to_execute"] is True


def test_active_operation_refuses_quit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    with store.startup_lock, store.lifetime_lock:
        store.publish(record)
        request = Mock(
            return_value=InstanceReply(
                app_id=record.app_id,
                instance_id=record.instance_id,
                challenge="test",
                accepted=True,
                active_operations=1,
            )
        )
        monkeypatch.setattr("pdomain_ocr_simple_gui.instance.request_instance", request)
        with pytest.raises(uninstall_support.UninstallPreparationError, match="operation is active"):
            uninstall_support._stop_verified_instance(tmp_path / "state")
    assert request.call_args.args == (record, "status")


def test_wrong_capability_refuses_uninstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    with store.startup_lock, store.lifetime_lock:
        store.publish(record)
        request = Mock(side_effect=ValueError("bad capability"))
        monkeypatch.setattr("pdomain_ocr_simple_gui.instance.request_instance", request)
        with pytest.raises(uninstall_support.UninstallPreparationError, match="native capability"):
            uninstall_support._stop_verified_instance(tmp_path / "state")


def test_stale_record_with_reused_pid_does_not_receive_quit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    with store.startup_lock, store.lifetime_lock:
        store.publish(record)
    request = Mock()
    monkeypatch.setattr("pdomain_ocr_simple_gui.instance.request_instance", request)

    uninstall_support._stop_verified_instance(tmp_path / "state")

    request.assert_not_called()


def test_uv_control_files_do_not_make_inventory_uncertain(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")
    (tools_root / ".gitignore").write_text("*\n", encoding="utf-8")
    (tools_root / ".lock").touch()

    assert _plan(suite_root, tools_root, own_environment).safe_to_execute is True


def test_malformed_registry_keeps_shared_integration_files(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    (suite_root / "installed.toml").write_text("[apps\nbroken = true\n", encoding="utf-8")
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")

    plan = _plan(suite_root, tools_root, own_environment)

    assert plan.safe_to_execute is False
    assert plan.reason == "unreadable_registry"


def test_quoted_own_registry_entry_does_not_count_as_other_app(tmp_path: Path) -> None:
    suite_root = tmp_path / "suite"
    suite_root.mkdir()
    (suite_root / "installed.toml").write_text(
        '[apps."pdomain-ocr-simple-gui"]\napp_id = "pdomain-ocr-simple-gui"\n', encoding="utf-8"
    )
    tools_root = tmp_path / "tools"
    own_environment = _environment(tools_root, "pdomain-ocr-simple-gui")

    assert _plan(suite_root, tools_root, own_environment).safe_to_execute is True


def test_prepare_uses_registry_canonical_root_and_stages_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ops.suite import paths as suite_paths
    from pdomain_ops.suite import registry as suite_registry

    state_root = tmp_path / "state"
    suite_root = tmp_path / "canonical-suite"
    locations = SimpleNamespace(
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        state_root=state_root,
        cache_root=tmp_path / "cache",
        projects_root=tmp_path / "projects",
        uploads_root=tmp_path / "uploads",
        outputs_root=tmp_path / "outputs",
        jobs_root=tmp_path / "jobs",
        overrides={},
    )
    unregistered: list[Path] = []

    def unregister(registry: object, app_id: str) -> None:
        assert app_id == uninstall_support.APP_ID
        unregistered.append(registry._path)

    monkeypatch.setattr("pdomain_ocr_simple_gui.locations.get_locations", lambda: locations)
    monkeypatch.setattr(uninstall_support, "_stop_verified_instance", lambda _root: None)
    monkeypatch.setattr(suite_paths, "installed_toml_path", lambda: suite_root / "installed.toml")
    monkeypatch.setattr(suite_registry.LocalTomlSuiteRegistry, "unregister", unregister)

    result = uninstall_support.prepare_uninstall(tmp_path / "tools")

    assert result["prepared"] is True
    assert result["suite_cleanup"]["suite_root"] == str(suite_root)
    assert unregistered == [suite_root / "installed.toml"]
    marker = Path(result["uninstall_marker"])
    assert marker.is_file()
    assert result["operation_token"] in marker.read_text(encoding="utf-8")
    resumed = uninstall_support.prepare_uninstall(tmp_path / "tools")
    assert resumed["operation_token"] == result["operation_token"]
    assert resumed["plan_path"] == result["plan_path"]


def test_prepare_failure_after_marker_cleans_only_its_own_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ops.suite import paths as suite_paths
    from pdomain_ops.suite import registry as suite_registry

    state_root = tmp_path / "state"
    locations = SimpleNamespace(
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        state_root=state_root,
        cache_root=tmp_path / "cache",
        projects_root=tmp_path / "projects",
        uploads_root=tmp_path / "uploads",
        outputs_root=tmp_path / "outputs",
        jobs_root=tmp_path / "jobs",
        overrides={},
    )
    monkeypatch.setattr("pdomain_ocr_simple_gui.locations.get_locations", lambda: locations)
    monkeypatch.setattr(uninstall_support, "_stop_verified_instance", lambda _root: None)
    monkeypatch.setattr(suite_paths, "installed_toml_path", lambda: tmp_path / "suite" / "installed.toml")
    monkeypatch.setattr(
        suite_registry.LocalTomlSuiteRegistry,
        "unregister",
        lambda _registry, _app_id: (_ for _ in ()).throw(OSError("registry unavailable")),
    )

    with pytest.raises(OSError, match="registry unavailable"):
        uninstall_support.prepare_uninstall(tmp_path / "tools")

    assert not (state_root / "uninstall-in-progress.json").exists()
    assert not tuple(state_root.glob("uninstall-finalize-*.py"))
    assert not tuple(state_root.glob("uninstall-plan-*.json"))


def test_unusable_base_python_fails_before_runtime_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "state"
    locations = SimpleNamespace(
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        state_root=state_root,
        cache_root=tmp_path / "cache",
        projects_root=tmp_path / "projects",
        uploads_root=tmp_path / "uploads",
        outputs_root=tmp_path / "outputs",
        jobs_root=tmp_path / "jobs",
        overrides={},
    )
    stopped = Mock()
    monkeypatch.setattr("pdomain_ocr_simple_gui.locations.get_locations", lambda: locations)
    monkeypatch.setattr(uninstall_support, "_stop_verified_instance", stopped)
    monkeypatch.setattr(
        uninstall_support.sys, "_base_executable", str(Path(uninstall_support.sys.prefix) / "python")
    )

    with pytest.raises(uninstall_support.UninstallPreparationError, match="base Python"):
        uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    assert not (state_root / "uninstall-in-progress.json").exists()


def _saved_project(projects_root: Path, output: Path, *, status_output: Path | None = None) -> Path:
    project_id = str(uuid4())
    directory = projects_root / project_id
    directory.mkdir()
    metadata = directory / "project.json"
    _ = metadata.write_text(
        json.dumps(
            {
                "spec": {
                    "project_id": project_id,
                    "name": "Saved OCR job",
                    "source_path": str(projects_root.parent / "external scans"),
                    "output_dir": str(output),
                    "engine": "doctr",
                    "language": "en",
                    "created_at": "2026-11-15T00:00:00Z",
                    "last_opened_at": "2026-11-15T00:00:00Z",
                },
                "status": {
                    "project_id": project_id,
                    "output_dir": str(status_output if status_output is not None else output),
                    "state": "succeeded",
                    "page_count": 1,
                    "pages_done": 1,
                    "pages": [],
                },
            }
        )
    )
    return metadata


@pytest.mark.parametrize("declared_in", ["spec", "status", "legacy_spec"])
def test_prepare_preserves_saved_outputs_inside_installation_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_in: str
) -> None:
    locations, installation, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    unsafe = installation / "old job output"
    unsafe.mkdir()
    _ = (unsafe / "ocr.txt").write_bytes(b"completed OCR must survive")
    safe = tmp_path / "external output"
    metadata = _saved_project(
        locations.projects_root,
        unsafe if declared_in in {"spec", "legacy_spec"} else safe,
        status_output=unsafe if declared_in == "status" else safe,
    )
    if declared_in == "legacy_spec":
        previous_id = metadata.parent.name
        legacy = metadata.parent.with_name("legacy-project")
        metadata.parent.rename(legacy)
        metadata = legacy / "project.json"
        _ = metadata.write_text(metadata.read_text().replace(previous_id, legacy.name))
    before = _snapshot_files(tmp_path)

    with pytest.raises(uninstall_support.UninstallPreparationError, match="moved first"):
        _ = uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    assert _snapshot_files(tmp_path) == before


@pytest.mark.parametrize("corruption", ["json", "schema", "wrong_project_id", "symlink"])
def test_prepare_refuses_unreadable_owned_job_metadata_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    locations, _, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    metadata = _saved_project(locations.projects_root, tmp_path / "safe output")
    if corruption == "json":
        _ = metadata.write_text('{"spec":')
    elif corruption == "schema":
        _ = metadata.write_text('{"spec": {}, "status": {}}')
    elif corruption == "wrong_project_id":
        _ = metadata.write_text(metadata.read_text().replace(metadata.parent.name, str(uuid4())))
    else:
        target = tmp_path / "foreign.json"
        metadata.rename(target)
        metadata.symlink_to(target)
    before = _snapshot_files(tmp_path)

    with pytest.raises(uninstall_support.UninstallPreparationError, match="project metadata"):
        _ = uninstall_support.prepare_uninstall(tmp_path / "tools")

    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    assert _snapshot_files(tmp_path) == before


def test_prepare_keeps_safe_external_job_outputs_and_ignores_unrelated_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locations, _, stopped, unregistered, _ = _retained_guard_setup(tmp_path, monkeypatch)
    safe = tmp_path / "external output"
    safe.mkdir()
    result_file = safe / "ocr.txt"
    _ = result_file.write_bytes(b"external OCR")
    metadata = _saved_project(locations.projects_root, safe)
    original = metadata.read_bytes()
    unrelated = locations.projects_root / "unrelated-folder"
    unrelated.mkdir()
    unrelated_metadata = unrelated / "project.json"
    _ = unrelated_metadata.write_bytes(b"unrelated data, not project metadata")
    unrelated_private = unrelated / "private.txt"
    _ = unrelated_private.write_bytes(b"do not inspect")
    nested = locations.projects_root / str(uuid4()) / "nested"
    nested.mkdir(parents=True)
    _ = (nested / "project.json").write_bytes(b"no recursive reading")
    original_read = Path.read_text

    def read_text(path: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if path in {unrelated_private, nested / "project.json"}:
            raise AssertionError("Unrelated folders must not be inspected")
        return original_read(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", read_text)

    result = uninstall_support.prepare_uninstall(tmp_path / "tools")

    assert result["prepared"] is True
    stopped.assert_called_once()
    unregistered.assert_called_once()
    assert metadata.read_bytes() == original
    assert result_file.read_bytes() == b"external OCR"
    assert unrelated_metadata.read_bytes() == b"unrelated data, not project metadata"


@pytest.mark.parametrize("source", ["configured_root", "saved_model_choice", "configured_locations"])
def test_prepare_reports_invalid_paths_without_removal_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    locations, _, stopped, unregistered, base = _retained_guard_setup(tmp_path, monkeypatch)
    invalid = "invalid\x00folder"
    if source == "configured_root":
        locations.data_root = Path(invalid)
    elif source == "saved_model_choice":
        _ = (locations.config_root / "preferences.json").write_text(
            json.dumps({"app": {"model_cache_location": invalid}})
        )
    else:
        getter = Mock(side_effect=ValueError("embedded null byte"))
        monkeypatch.setattr("pdomain_ocr_simple_gui.locations.get_locations", getter)
    before = _snapshot_files(tmp_path)

    exit_code = uninstall_support.main(["--prepare", "--tool-dir", str(tmp_path / "tools"), "--json"])

    assert exit_code != 0
    assert "Uninstall preparation failed" in capsys.readouterr().err
    stopped.assert_not_called()
    unregistered.assert_not_called()
    base.assert_not_called()
    assert _snapshot_files(tmp_path) == before
