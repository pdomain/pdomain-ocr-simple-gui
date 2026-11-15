"""External-server acceptance behavior."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

import scripts.windows_acceptance as acceptance
from scripts.windows_acceptance import AcceptanceError, Fixture, Recorder, ServerOrigin, parse_args

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_args_accepts_a_loopback_origin_with_an_explicit_port() -> None:
    args = parse_args(["--url", "http://127.0.0.1:8004/"])

    assert args.url == ServerOrigin(host="127.0.0.1", port=8004)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8004",
        "http://localhost:8004",
        "http://127.0.0.1",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://user:pass@127.0.0.1:8004",
        "http://127.0.0.1:8004/jobs",
        "http://127.0.0.1:8004/?debug=1",
        "http://127.0.0.1:8004/#top",
    ],
)
def test_parse_args_rejects_an_unsupported_external_server_url(url: str) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(["--url", url])


def test_parse_args_rejects_an_executable_with_an_external_server_url() -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(["--exe", "installed-app.exe", "--url", "http://127.0.0.1:8004"])


def _external_args(tmp_path: Path) -> tuple[acceptance.AcceptanceArgs, Fixture]:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    image = fixtures / "known_good_page.png"
    truth = fixtures / "known_good_page.gt.txt"
    _ = image.write_bytes(b"png")
    _ = truth.write_text("known text", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    args = parse_args(
        [
            "--fixtures",
            str(fixtures),
            "--out-dir",
            str(out_dir),
            "--url",
            "http://127.0.0.1:8004/",
        ]
    )
    return args, Fixture(image=image, truth=truth)


def _unexpected(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("the external-server branch must not create or discover a server")


def test_run_with_url_uses_the_existing_server_without_process_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, fixture = _external_args(tmp_path)
    observed: list[tuple[str, ServerOrigin]] = []

    def ready(server: ServerOrigin) -> None:
        observed.append(("ready", server))

    def probe(_rec: Recorder, server: ServerOrigin) -> None:
        observed.append(("probe", server))

    def browser(
        _rec: Recorder, _args: acceptance.AcceptanceArgs, actual: Fixture, server: ServerOrigin
    ) -> None:
        assert actual == fixture
        observed.append(("browser", server))

    monkeypatch.setattr(shutil, "which", _unexpected)
    monkeypatch.setattr(subprocess, "Popen", _unexpected)
    monkeypatch.setattr(acceptance, "wait_for_server", ready)
    monkeypatch.setattr(acceptance, "probe_server", probe)
    monkeypatch.setattr(acceptance, "drive_browser", browser)

    rec = Recorder()
    acceptance.run(args, rec)

    origin = ServerOrigin(host="127.0.0.1", port=8004)
    assert observed == [("ready", origin), ("probe", origin), ("browser", origin)]
    assert len(rec.steps) == 1
    assert rec.steps[0]["step"] == "server-up"
    assert rec.steps[0]["url"] == origin.url
    assert rec.steps[0]["ownership"] == "external"


def test_run_with_url_leaves_the_existing_server_unowned_when_a_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _fixture = _external_args(tmp_path)

    def ready(_server: ServerOrigin) -> None:
        return None

    def failed_probe(_rec: Recorder, _server: ServerOrigin) -> None:
        raise AcceptanceError("probe failed")

    monkeypatch.setattr(shutil, "which", _unexpected)
    monkeypatch.setattr(subprocess, "Popen", _unexpected)
    monkeypatch.setattr(acceptance, "wait_for_server", ready)
    monkeypatch.setattr(acceptance, "probe_server", failed_probe)

    with pytest.raises(AcceptanceError, match="probe failed"):
        acceptance.run(args, Recorder())


class _OwnedProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.terminated: bool = False
        self.waited: bool = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> int:
        assert timeout == 20
        self.waited = True
        return 0

    def kill(self) -> None:
        raise AssertionError("a normally stopped owned server must not be killed")


def test_run_without_url_keeps_the_owned_server_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, fixture = _external_args(tmp_path)
    args = acceptance.AcceptanceArgs(
        out_dir=args.out_dir,
        fixtures=args.fixtures,
        browser_channel=args.browser_channel,
        headless=args.headless,
        exe="installed-app.exe",
        url=None,
        skip_text_quality=args.skip_text_quality,
    )
    process = _OwnedProcess()
    commands: list[list[str]] = []
    observed: list[tuple[str, ServerOrigin]] = []

    def start(command: list[str], **_kwargs: object) -> _OwnedProcess:
        commands.append(command)
        return process

    def ready(actual: _OwnedProcess, server: ServerOrigin) -> None:
        assert actual is process
        observed.append(("ready", server))

    def probe(_rec: Recorder, server: ServerOrigin) -> None:
        observed.append(("probe", server))

    def browser(
        _rec: Recorder, _args: acceptance.AcceptanceArgs, actual: Fixture, server: ServerOrigin
    ) -> None:
        assert actual == fixture
        observed.append(("browser", server))

    monkeypatch.setattr(acceptance, "free_port", lambda: 8123)
    monkeypatch.setattr(subprocess, "Popen", start)
    monkeypatch.setattr(acceptance, "wait_for_owned_server", ready)
    monkeypatch.setattr(acceptance, "probe_server", probe)
    monkeypatch.setattr(acceptance, "drive_browser", browser)

    acceptance.run(args, Recorder())

    origin = ServerOrigin(host="127.0.0.1", port=8123)
    assert commands == [["installed-app.exe", "--no-browser", "--port", "8123"]]
    assert observed == [("ready", origin), ("probe", origin), ("browser", origin)]
    assert process.terminated
    assert process.waited
