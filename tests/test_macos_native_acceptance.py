"""Failure boundaries for the macOS native artifact test driver."""

from __future__ import annotations

import http.client
import json
import subprocess
from pathlib import Path

import pytest

from scripts import macos_native_acceptance as native


def _empty_command(_argv: list[str], *, timeout: float = 30) -> str:
    del timeout
    return ""


def test_native_open_requires_explicit_environment_support(monkeypatch: pytest.MonkeyPatch) -> None:
    def command(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "usage: open [-a application]", "")

    monkeypatch.setattr(subprocess, "run", command)
    with pytest.raises(native.AcceptanceError, match="--env"):
        native.verify_open_environment_support()


def test_ocr_exit_zero_without_result_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "command", _empty_command)
    with pytest.raises(native.AcceptanceError, match="result"):
        _ = native.run_ocr(tmp_path, tmp_path / "out", "http://127.0.0.1:8004")


def test_ocr_failed_result_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "command", _empty_command)
    output = tmp_path / "out/ocr"
    output.mkdir(parents=True)
    _ = (output / "results.json").write_text(json.dumps({"passed": False}))
    with pytest.raises(native.AcceptanceError, match="report PASS"):
        _ = native.run_ocr(tmp_path, tmp_path / "out", "http://127.0.0.1:8004")


def test_ocr_reads_successful_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "command", _empty_command)
    output = tmp_path / "out/ocr"
    output.mkdir(parents=True)
    _ = (output / "results.json").write_text(json.dumps({"passed": True, "seconds": 1.0}))
    assert native.run_ocr(tmp_path, tmp_path / "out", "http://127.0.0.1:8004")["passed"] is True


def test_snapshot_rejects_symlinks_outside_the_test_root(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    outside = tmp_path / "unrelated"
    _ = outside.write_text("retain")
    (data / "alias").symlink_to(outside)
    with pytest.raises(native.AcceptanceError, match="symlink"):
        _ = native.snapshot_files([data])


def test_retention_detects_changed_data(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    file = data / "page.txt"
    _ = file.write_text("OCR output")
    before = native.snapshot_files([data])
    _ = file.write_text("changed")
    with pytest.raises(native.AcceptanceError, match="changed"):
        native.verify_retained(before)


def test_command_timeout_remains_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("osascript", 1)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.TimeoutExpired):
        _ = native.command(["/usr/bin/osascript"], timeout=1)


def test_existing_application_is_not_overwritten(tmp_path: Path) -> None:
    config = native.Configuration(
        repo=tmp_path,
        installer=tmp_path / "installer.app",
        work=tmp_path / "work",
        output=tmp_path / "out",
        home=tmp_path / "home",
    )
    application = config.application
    application.mkdir(parents=True)
    with pytest.raises(native.AcceptanceError, match="already exists"):
        config.check_fresh_installation()
    assert application.is_dir()


def test_nonzero_command_includes_native_error_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 7, "", "native permission denied")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(native.AcceptanceError, match="native permission denied"):
        _ = native.command(["/usr/bin/osascript"])


def test_failure_still_writes_a_failed_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = native.Configuration(
        repo=tmp_path,
        installer=tmp_path / "installer.app",
        work=tmp_path / "work",
        output=tmp_path / "out",
        home=tmp_path / "home",
    )

    def fail(_self: native.NativeAcceptance) -> None:
        raise native.AcceptanceError("GUI permission unavailable")

    def no_screenshot(_self: native.NativeAcceptance, _name: str) -> None:
        return None

    monkeypatch.setattr(native.NativeAcceptance, "prepare", fail)
    monkeypatch.setattr(native.NativeAcceptance, "screenshot", no_screenshot)
    with pytest.raises(native.AcceptanceError, match="GUI permission unavailable"):
        native.NativeAcceptance(config).run()
    result = native.read_object(config.output / "results.json")
    assert result["passed"] is False
    assert result["error"] == "GUI permission unavailable"


def test_non_cpu_backend_is_rejected_before_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class Response:
        status: int = 200

        def read(self) -> bytes:
            return b'{"detected_device":"mps"}'

    class Connection:
        def __init__(self, _host: str, _port: int | None, *, timeout: float) -> None:
            del timeout

        def request(self, _method: str, _path: str) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    config = native.Configuration(
        repo=tmp_path,
        installer=tmp_path / "installer.app",
        work=tmp_path / "work",
        output=tmp_path / "out",
        home=tmp_path / "home",
    )
    record_path = tmp_path / "instance.json"
    _ = record_path.write_text(
        json.dumps(
            {"instance_id": "1" * 32, "pid": 42, "origin": "http://127.0.0.1:8004", "capability": "2" * 64}
        )
    )
    record = native.load_record(record_path)
    with pytest.raises(native.AcceptanceError, match="CPU"):
        native.NativeAcceptance(config).verify_cpu(record)
    assert closed == [True]


def test_failed_native_command_does_not_create_an_ocr_pass_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_argv: list[str], *, timeout: float = 30) -> str:
        del timeout
        raise native.AcceptanceError("interrupted process")

    monkeypatch.setattr(native, "command", fail)
    with pytest.raises(native.AcceptanceError, match="interrupted process"):
        _ = native.run_ocr(tmp_path, tmp_path / "out", "http://127.0.0.1:8004")
    assert not (tmp_path / "out/ocr/results.json").exists()
