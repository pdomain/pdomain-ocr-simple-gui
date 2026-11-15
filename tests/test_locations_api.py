"""Expose effective paths and serialize data relocation against app work."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.activity_gate import StorageGate
from pdomain_ocr_simple_gui.app import create_app

if TYPE_CHECKING:
    from collections.abc import Callable


def _installed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, platform: str = "linux"
) -> Callable[[str], Path]:
    import pdomain_ocr_simple_gui.routes.locations as locations_routes

    environment = tmp_path / "tool environment"
    binary_dir = environment / ("Scripts" if platform == "win32" else "bin")
    binary_dir.mkdir(parents=True)
    monkeypatch.setattr(
        locations_routes,
        "sys",
        SimpleNamespace(
            executable=str(binary_dir / ("pythonw.exe" if platform == "win32" else "python")),
            prefix=str(environment),
            base_prefix=str(tmp_path / "base python"),
            platform=platform,
        ),
    )

    def missing_command(_command: str) -> None:
        return None

    monkeypatch.setattr(locations_routes, "shutil", SimpleNamespace(which=missing_command))
    for variable in ("UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def executable(name: str) -> Path:
        target = binary_dir / name
        _ = target.write_bytes(b"installed executable")
        target.chmod(0o755)
        return target

    return executable


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_location_report_finds_launcher_beside_tool_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    executable = _installed_environment(tmp_path, monkeypatch, platform=platform)
    target = executable("pdomain-ocr-simple-gui-desktop" + (".exe" if platform == "win32" else ""))
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["installation"]["desktop_launcher"] == str(target)


@pytest.mark.parametrize("kind", ["missing", "nonexecutable", "directory"])
def test_location_report_does_not_invent_missing_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    executable = _installed_environment(tmp_path, monkeypatch)
    if kind == "nonexecutable":
        executable("pdomain-ocr-simple-gui-desktop").chmod(0o644)
    elif kind == "directory":
        target = executable("pdomain-ocr-simple-gui-desktop")
        target.unlink()
        target.mkdir()
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["installation"]["desktop_launcher"] == ""
    assert response.json()["installation"]["uv"] == ""


@pytest.mark.parametrize(
    "setting", ["default", "UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME", "XDG_DATA_HOME"]
)
@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_location_report_finds_uv_in_configured_executable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str, platform: str
) -> None:
    _ = _installed_environment(tmp_path, monkeypatch, platform=platform)
    directory = tmp_path / "home/.local/bin"
    if setting == "XDG_DATA_HOME":
        directory = tmp_path / "custom data/bin"
        monkeypatch.setenv(setting, str(tmp_path / "custom data/share"))
        (tmp_path / "custom data/share").mkdir(parents=True)
    elif setting != "default":
        directory = tmp_path / "custom bin"
        monkeypatch.setenv(setting, str(directory))
    directory.mkdir(parents=True)
    target = directory / ("uv.exe" if platform == "win32" else "uv")
    _ = target.write_bytes(b"installed uv")
    target.chmod(0o755)
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    expected = target
    if setting == "XDG_DATA_HOME":
        expected = tmp_path / "custom data/share/../bin" / target.name
    assert response.json()["installation"]["uv"] == str(expected)


def test_location_report_does_not_report_nonexecutable_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _installed_environment(tmp_path, monkeypatch)
    directory = tmp_path / "custom bin"
    directory.mkdir()
    _ = (directory / "uv").write_bytes(b"not executable")
    monkeypatch.setenv("UV_INSTALL_DIR", str(directory))
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["installation"]["uv"] == ""


def test_location_report_respects_uv_override_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _installed_environment(tmp_path, monkeypatch)
    for variable in ("UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME"):
        directory = tmp_path / variable
        directory.mkdir()
        target = directory / "uv"
        _ = target.write_bytes(b"installed uv")
        target.chmod(0o755)
        monkeypatch.setenv(variable, str(directory))
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["installation"]["uv"] == str(tmp_path / "UV_UNMANAGED_INSTALL/uv")


def test_location_report_prefers_executables_available_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pdomain_ocr_simple_gui.routes.locations as locations_routes

    executable = _installed_environment(tmp_path, monkeypatch)
    _ = executable("pdomain-ocr-simple-gui-desktop")
    commands = {
        "pdomain-ocr-simple-gui-desktop": str(tmp_path / "native launcher"),
        "uv": str(tmp_path / "package manager"),
    }
    for filename in commands.values():
        target = Path(filename)
        _ = target.write_bytes(b"installed executable")
        target.chmod(0o755)
    monkeypatch.setattr(locations_routes, "shutil", SimpleNamespace(which=commands.get))
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["installation"]["desktop_launcher"] == commands["pdomain-ocr-simple-gui-desktop"]
    assert response.json()["installation"]["uv"] == commands["uv"]


def test_settings_reports_effective_roots_and_override_sources() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/locations")
    assert response.status_code == 200
    result = response.json()
    assert set(result["paths"]) >= {"data", "config", "state", "projects", "uploads", "outputs", "jobs"}
    assert result["overrides"]["projects"] == "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"
    assert result["installation"]["python"]


def test_migration_refuses_an_active_request_before_writing(tmp_path: Path) -> None:
    app = create_app()
    gate = StorageGate()
    app.state.storage_gate = gate
    destination = tmp_path / "destination"
    with TestClient(app) as client, gate.activity():
        response = client.post("/api/locations/migrate", json={"destination": str(destination)})
    assert response.status_code == 409
    assert not destination.exists()


def test_active_migration_blocks_storage_work_but_status_stays_available() -> None:
    app = create_app()
    gate = StorageGate()
    app.state.storage_gate = gate
    with TestClient(app) as client, gate.exclusive():
        assert client.get("/api/jobs").status_code == 409
        response = client.get("/api/locations")
        assert response.status_code == 200
        assert response.json()["migration_in_progress"] is True


def test_location_report_survives_a_contended_preferences_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdomain_ops.suite.prefs import PrefsLockTimeout

    import pdomain_ocr_simple_gui.app as app_module

    with TestClient(create_app()) as client:
        adapter = Mock()
        adapter.read.side_effect = PrefsLockTimeout(str(tmp_path / "prefs.lock"), 0.1)
        monkeypatch.setattr(app_module, "_prefs_adapter", adapter)
        response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json()["requested_model_cache"] == ""
    assert response.json()["model_cache_restart_required"] is False
