# tests/test_container_detect.py
from pathlib import Path

from pd_ocr_simple_gui.runtime.container_detect import detect_containerized


def test_dockerenv_marker(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / ".dockerenv"
    marker.touch()
    monkeypatch.setattr("pd_ocr_simple_gui.runtime.container_detect._DOCKERENV", marker)
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._PODMAN_MARKER",
        tmp_path / "missing",
    )
    monkeypatch.delenv("container", raising=False)
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._read_init_cgroup",
        lambda: "",
    )
    assert detect_containerized() is True


def test_podman_marker(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "containerenv"
    marker.touch()
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._DOCKERENV",
        tmp_path / "missing",
    )
    monkeypatch.setattr("pd_ocr_simple_gui.runtime.container_detect._PODMAN_MARKER", marker)
    monkeypatch.delenv("container", raising=False)
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._read_init_cgroup",
        lambda: "",
    )
    assert detect_containerized() is True


def test_container_env_var(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._DOCKERENV",
        tmp_path / "missing",
    )
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._PODMAN_MARKER",
        tmp_path / "missing2",
    )
    monkeypatch.setenv("container", "podman")
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._read_init_cgroup",
        lambda: "",
    )
    assert detect_containerized() is True


def test_cgroup_signal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._DOCKERENV",
        tmp_path / "missing",
    )
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._PODMAN_MARKER",
        tmp_path / "missing2",
    )
    monkeypatch.delenv("container", raising=False)
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._read_init_cgroup",
        lambda: "12:cpuset:/docker/abcd",
    )
    assert detect_containerized() is True


def test_none_match(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._DOCKERENV",
        tmp_path / "missing",
    )
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._PODMAN_MARKER",
        tmp_path / "missing2",
    )
    monkeypatch.delenv("container", raising=False)
    monkeypatch.setattr(
        "pd_ocr_simple_gui.runtime.container_detect._read_init_cgroup",
        lambda: "12:cpuset:/user.slice",
    )
    assert detect_containerized() is False
