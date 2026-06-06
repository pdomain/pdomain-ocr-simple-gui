"""Tests for the Linux installer engine.

These tests are pure-Python (no subprocess execution) and always run as part
of the normal pytest suite.  They validate: distro detection, package mapping,
step planning, and the interactive runner (fake ask + fake run_cmd).

NOTE: The engine lives at ``installer/install_engine.py`` (not ``packaging/``)
because the PyPI ``packaging`` namespace is already registered as a regular
package in the venv, blocking namespace-package merging.  ``installer/`` is
added to sys.path via ``pyproject.toml`` ``pythonpath = ['.']``, so
``from installer.install_engine import`` resolves correctly under pytest.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from installer.install_engine import (
    Step,
    _build_exec_args,
    detect_nvidia,
    detect_pkg_manager,
    plan_steps,
    run,
    webview_package_for,
)

# ---------------------------------------------------------------------------
# detect_pkg_manager
# ---------------------------------------------------------------------------


def test_detect_pkg_manager_apt(monkeypatch: pytest.MonkeyPatch) -> None:
    """apt present → returns 'apt'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "apt")
    assert detect_pkg_manager() == "apt"


def test_detect_pkg_manager_dnf(monkeypatch: pytest.MonkeyPatch) -> None:
    """dnf present → returns 'dnf'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "dnf")
    assert detect_pkg_manager() == "dnf"


def test_detect_pkg_manager_pacman(monkeypatch: pytest.MonkeyPatch) -> None:
    """pacman present → returns 'pacman'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "pacman")
    assert detect_pkg_manager() == "pacman"


def test_detect_pkg_manager_zypper(monkeypatch: pytest.MonkeyPatch) -> None:
    """zypper present → returns 'zypper'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "zypper")
    assert detect_pkg_manager() == "zypper"


def test_detect_pkg_manager_apk(monkeypatch: pytest.MonkeyPatch) -> None:
    """apk present → returns 'apk'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "apk")
    assert detect_pkg_manager() == "apk"


def test_detect_pkg_manager_yum(monkeypatch: pytest.MonkeyPatch) -> None:
    """yum only (no dnf) → returns 'yum'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "yum")
    assert detect_pkg_manager() == "yum"


def test_detect_pkg_manager_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing found → returns None."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: False)
    assert detect_pkg_manager() is None


def test_detect_pkg_manager_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """apt wins over yum when both present (apt checked first)."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x in ("apt", "yum"))
    assert detect_pkg_manager() == "apt"


# ---------------------------------------------------------------------------
# webview_package_for
# ---------------------------------------------------------------------------


def test_webview_package_mapping() -> None:
    """Qt xcb-cursor: apt → libxcb-cursor0, pacman → xcb-util-cursor, unknown → None."""
    assert webview_package_for("apt") == "libxcb-cursor0"
    assert webview_package_for("pacman") == "xcb-util-cursor"
    assert webview_package_for("unknown") is None


def test_webview_package_fedora() -> None:
    """dnf → xcb-util-cursor (Fedora 39+)."""
    assert webview_package_for("dnf") == "xcb-util-cursor"


def test_webview_package_yum() -> None:
    """yum → xcb-util-cursor (same as dnf)."""
    assert webview_package_for("yum") == "xcb-util-cursor"


def test_webview_package_zypper() -> None:
    """zypper → libxcb-cursor0 (openSUSE)."""
    assert webview_package_for("zypper") == "libxcb-cursor0"


def test_webview_package_apk() -> None:
    """apk → xcb-util-cursor (Alpine)."""
    assert webview_package_for("apk") == "xcb-util-cursor"


def test_webview_package_none() -> None:
    """None input → None (unknown distro)."""
    assert webview_package_for(None) is None


# ---------------------------------------------------------------------------
# detect_nvidia
# ---------------------------------------------------------------------------


def test_detect_nvidia_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi found with driver >= 525 → returns 'nvidia'."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "535.154.05")
    assert detect_nvidia() == "nvidia"


def test_detect_nvidia_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi absent → returns None."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: False)
    assert detect_nvidia() is None


# ---------------------------------------------------------------------------
# plan_steps
# ---------------------------------------------------------------------------


def test_plan_steps_includes_gated_actions() -> None:
    """Plan contract: all flags off + nvidia → all 5 step ids in order."""
    steps = plan_steps(has_uv=False, has_webview=False, gpu="nvidia")
    ids = [s.id for s in steps]
    assert ids == ["uv", "webview", "tool_install", "gpu_torch", "shortcut"]
    assert all(s.command for s in steps)  # each gated step has an explicit command


def test_plan_steps_webview_command_contains_xcb_cursor_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """webview step command references the Qt xcb-cursor package (not WebKitGTK)."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "apt")
    steps = plan_steps(has_uv=True, has_webview=False, gpu=None, mgr="apt")
    webview = next(s for s in steps if s.id == "webview")
    assert isinstance(webview.command, str)
    assert "libxcb-cursor0" in webview.command
    assert "webkit" not in webview.command.lower()


def test_plan_steps_webview_unknown_distro_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown distro → webview command is a comment with xcb-cursor guidance."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: False)
    steps = plan_steps(has_uv=True, has_webview=False, gpu=None, mgr=None)
    webview = next(s for s in steps if s.id == "webview")
    assert isinstance(webview.command, str)
    assert webview.command.startswith("#")
    assert "xcb-cursor" in webview.command.lower() or "xcb" in webview.command.lower()


def test_plan_steps_skips_uv_when_present() -> None:
    """has_uv=True → uv step absent."""
    steps = plan_steps(has_uv=True, has_webview=False, gpu=None)
    ids = [s.id for s in steps]
    assert "uv" not in ids
    assert "tool_install" in ids


def test_plan_steps_skips_webview_when_present() -> None:
    """has_webview=True → webview step absent."""
    steps = plan_steps(has_uv=False, has_webview=True, gpu=None)
    ids = [s.id for s in steps]
    assert "webview" not in ids
    assert "tool_install" in ids


def test_plan_steps_skips_gpu_when_no_nvidia() -> None:
    """gpu != 'nvidia' → gpu_torch step absent."""
    steps = plan_steps(has_uv=True, has_webview=True, gpu=None)
    ids = [s.id for s in steps]
    assert "gpu_torch" not in ids


def test_plan_steps_tool_install_always_present() -> None:
    """tool_install always present regardless of flags."""
    steps = plan_steps(has_uv=True, has_webview=True, gpu="nvidia")
    ids = [s.id for s in steps]
    assert "tool_install" in ids


def test_plan_steps_all_steps_have_required_fields() -> None:
    """All Step objects have non-empty id, description, command."""
    steps = plan_steps(has_uv=False, has_webview=False, gpu="nvidia")
    for step in steps:
        assert step.id, f"Step missing id: {step}"
        assert step.description, f"Step {step.id} missing description"
        assert step.command, f"Step {step.id} missing command"
        assert isinstance(step.needs_sudo, bool), f"Step {step.id} needs_sudo not bool"


def test_plan_steps_webview_includes_sudo() -> None:
    """webview step needs sudo (package manager install)."""
    steps = plan_steps(has_uv=False, has_webview=False, gpu=None)
    webview = next(s for s in steps if s.id == "webview")
    assert webview.needs_sudo is True


def test_plan_steps_minimal() -> None:
    """All already present + no GPU → only tool_install and shortcut."""
    steps = plan_steps(has_uv=True, has_webview=True, gpu=None)
    ids = [s.id for s in steps]
    assert ids == ["tool_install", "shortcut"]


# ---------------------------------------------------------------------------
# run() — interactive runner
# ---------------------------------------------------------------------------


def test_run_dry_run_no_execution() -> None:
    """dry_run=True → prints steps but never calls run_cmd."""
    calls: list[Any] = []
    steps = [
        Step(id="tool_install", description="Install", command="uv tool install foo", needs_sudo=False),
    ]

    def _recording_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:  # type: ignore[type-arg]
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    run(steps, assume_yes=True, dry_run=True, run_cmd=_recording_run)
    assert calls == []


def test_run_assume_yes_executes_all() -> None:
    """assume_yes=True → all steps execute without calling ask."""
    executed: list[str] = []
    ask_calls: list[str] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:  # type: ignore[type-arg]
        executed.append(cmd[0] if cmd else "")
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    steps = [
        Step(
            id="uv",
            description="Install uv",
            command="curl -LsSf https://astral.sh/uv/install.sh | sh",
            needs_sudo=False,
        ),
        Step(id="tool_install", description="Install app", command="uv tool install app", needs_sudo=False),
    ]
    run(steps, assume_yes=True, dry_run=False, ask=lambda p: ask_calls.append(p) or "y", run_cmd=fake_run)
    assert len(executed) == 2
    assert ask_calls == []


def test_run_user_says_no_skips_step() -> None:
    """User answers 'n' → step skipped."""
    executed: list[str] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:  # type: ignore[type-arg]
        executed.append(cmd[0] if cmd else "")
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    steps = [
        Step(id="tool_install", description="Install app", command="uv tool install app", needs_sudo=False),
    ]
    run(steps, assume_yes=False, dry_run=False, ask=lambda _p: "n", run_cmd=fake_run)
    assert executed == []


def test_run_user_says_yes_executes() -> None:
    """User answers 'y' → step executes."""
    executed: list[str] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:  # type: ignore[type-arg]
        executed.append("ok")
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    steps = [
        Step(id="tool_install", description="Install app", command="uv tool install app", needs_sudo=False),
    ]
    run(steps, assume_yes=False, dry_run=False, ask=lambda _p: "y", run_cmd=fake_run)
    assert executed == ["ok"]


def test_run_sudo_prefix_when_needs_sudo() -> None:
    """Step.needs_sudo=True → command is prefixed with sudo."""
    commands_seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:  # type: ignore[type-arg]
        commands_seen.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    steps = [
        Step(
            id="webview",
            description="Install Qt xcb-cursor lib",
            command="apt-get install -y libxcb-cursor0",
            needs_sudo=True,
        ),
    ]
    run(steps, assume_yes=True, dry_run=False, run_cmd=fake_run)
    assert commands_seen[0][0] == "sudo"


def test_step_dataclass() -> None:
    """Step is a dataclass-like with the expected fields."""
    s = Step(id="x", description="desc", command="cmd", needs_sudo=False)
    assert s.id == "x"
    assert s.description == "desc"
    assert s.command == "cmd"
    assert s.needs_sudo is False


# ---------------------------------------------------------------------------
# _build_exec_args — pipe safety and sudo prepend
# ---------------------------------------------------------------------------


def test_build_exec_args_uv_step_no_bare_pipe() -> None:
    """uv step uses list command — built argv must NOT contain a bare '|' token.

    This guards against the regression where the command was a string and
    shlex.split turned '|' into a literal curl argument, making the install
    silently fail.
    """
    uv_step = Step(
        id="uv",
        description="Install uv",
        command=["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
        needs_sudo=False,
    )
    argv = _build_exec_args(uv_step)
    assert "|" not in argv, f"Bare pipe token found in argv: {argv}"
    assert argv[0] == "sh"
    assert argv[1] == "-c"
    assert "curl" in argv[2]


def test_build_exec_args_uv_step_valid_argv() -> None:
    """uv step argv is ['sh', '-c', '...'] — three tokens, no bare pipe."""
    uv_step = Step(
        id="uv",
        description="Install uv",
        command=["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
        needs_sudo=False,
    )
    argv = _build_exec_args(uv_step)
    assert len(argv) == 3  # ["sh", "-c", "curl ... | sh"]


def test_build_exec_args_sudo_step_prepends_sudo() -> None:
    """needs_sudo=True → 'sudo' is first token for both str and list commands."""
    # str command
    str_step = Step(
        id="webview",
        description="Install Qt xcb-cursor lib",
        command="apt-get install -y libxcb-cursor0",
        needs_sudo=True,
    )
    argv = _build_exec_args(str_step)
    assert argv[0] == "sudo"
    assert argv[1] == "apt-get"

    # list command
    list_step = Step(
        id="webview",
        description="Install Qt xcb-cursor lib",
        command=["apt-get", "install", "-y", "libxcb-cursor0"],
        needs_sudo=True,
    )
    argv2 = _build_exec_args(list_step)
    assert argv2[0] == "sudo"
    assert argv2[1] == "apt-get"


def test_build_exec_args_no_sudo_does_not_prepend() -> None:
    """needs_sudo=False → no 'sudo' prefix for either str or list command."""
    step = Step(id="tool_install", description="Install", command="uv tool install app", needs_sudo=False)
    argv = _build_exec_args(step)
    assert argv[0] != "sudo"
    assert argv[0] == "uv"


# ---------------------------------------------------------------------------
# detect_nvidia — driver version gate (spec §7.3)
# ---------------------------------------------------------------------------


def test_detect_nvidia_absent_no_smi(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi not on PATH → returns None (no GPU, no driver check)."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: False)
    assert detect_nvidia() is None


def test_detect_nvidia_driver_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi present + driver >= 525 → returns 'nvidia'; gpu_torch included."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "535.154.05")
    result = detect_nvidia()
    assert result == "nvidia"

    steps = plan_steps(has_uv=True, has_webview=True, gpu=result)
    ids = [s.id for s in steps]
    assert "gpu_torch" in ids


def test_detect_nvidia_driver_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi present + driver < 525 → returns None; gpu_torch absent from plan."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "470.256.02")
    result = detect_nvidia()
    assert result is None

    steps = plan_steps(has_uv=True, has_webview=True, gpu=result)
    ids = [s.id for s in steps]
    assert "gpu_torch" not in ids


def test_detect_nvidia_driver_query_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi present but version query returns None → returns None safely."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: None)
    assert detect_nvidia() is None


def test_detect_nvidia_driver_exactly_at_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Driver exactly at 525 → 'nvidia' (boundary: >= not >)."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "525.0.0")
    assert detect_nvidia() == "nvidia"


def test_detect_nvidia_plan_includes_driver_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Below-threshold driver prints guidance message to stdout."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "470.0.0")
    detect_nvidia()
    captured = capsys.readouterr()
    assert "525" in captured.out
    assert "driver" in captured.out.lower()
