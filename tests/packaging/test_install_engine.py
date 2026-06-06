"""Tests for the Linux installer engine.

These tests are pure-Python (no subprocess execution) and always run as part
of the normal pytest suite.  They validate: distro detection, step planning,
and the interactive runner (fake ask + fake run_cmd).

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
    PD_INDEX_URL,
    Step,
    _build_exec_args,
    _query_cuda_version,
    cuda_supports_book_tools_gpu,
    cuda_tag_for,
    detect_nvidia,
    detect_pkg_manager,
    display_command,
    plan_steps,
    run,
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
# plan_steps — browser-only: no webview step
# ---------------------------------------------------------------------------


def test_plan_steps_no_webview_step() -> None:
    """Browser-only installer: webview step must NEVER appear in the plan."""
    for has_uv_val in [True, False]:
        for gpu_val in [None, "nvidia"]:
            steps = plan_steps(has_uv=has_uv_val, gpu=gpu_val, cuda_tag="cu130")
            ids = [s.id for s in steps]
            assert "webview" not in ids, f"webview step found for has_uv={has_uv_val}, gpu={gpu_val}: {ids}"


def test_plan_steps_includes_gated_actions() -> None:
    """Plan contract: uv + nvidia + cuda_tag → uv/tool_install/shortcut (no webview, no gpu_torch)."""
    steps = plan_steps(has_uv=False, gpu="nvidia", cuda_tag="cu121")
    ids = [s.id for s in steps]
    assert ids == ["uv", "tool_install", "shortcut"]
    assert all(s.command for s in steps)


def test_plan_steps_skips_uv_when_present() -> None:
    """has_uv=True → uv step absent."""
    steps = plan_steps(has_uv=True, gpu=None)
    ids = [s.id for s in steps]
    assert "uv" not in ids
    assert "tool_install" in ids


def test_plan_steps_skips_gpu_when_no_nvidia() -> None:
    """gpu != 'nvidia' → gpu_torch step absent."""
    steps = plan_steps(has_uv=True, gpu=None)
    ids = [s.id for s in steps]
    assert "gpu_torch" not in ids


def test_plan_steps_tool_install_always_present() -> None:
    """tool_install always present regardless of flags."""
    steps = plan_steps(has_uv=True, gpu="nvidia")
    ids = [s.id for s in steps]
    assert "tool_install" in ids


def test_plan_steps_all_steps_have_required_fields() -> None:
    """All Step objects have non-empty id, description, command."""
    steps = plan_steps(has_uv=False, gpu="nvidia")
    for step in steps:
        assert step.id, f"Step missing id: {step}"
        assert step.description, f"Step {step.id} missing description"
        assert step.command, f"Step {step.id} missing command"
        assert isinstance(step.needs_sudo, bool), f"Step {step.id} needs_sudo not bool"


def test_plan_steps_minimal() -> None:
    """All already present + no GPU → only tool_install and shortcut."""
    steps = plan_steps(has_uv=True, gpu=None)
    ids = [s.id for s in steps]
    assert ids == ["tool_install", "shortcut"]


# ---------------------------------------------------------------------------
# plan_steps — plain package (no [desktop] extra)
# ---------------------------------------------------------------------------


def test_tool_install_uses_plain_package() -> None:
    """tool_install command must use plain 'pdomain-ocr-simple-gui', not '[desktop]' variant."""
    steps = plan_steps(has_uv=True, gpu=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    # The package argument should be plain, without any extra
    assert "pdomain-ocr-simple-gui" in argv
    # [desktop] must NOT appear anywhere in the command
    assert not any("[desktop]" in token for token in argv), (
        f"[desktop] extra found in tool_install command: {argv}"
    )


def test_tool_install_uses_reinstall() -> None:
    """tool_install passes --reinstall so re-running the installer upgrades (not a no-op)."""
    steps = plan_steps(has_uv=True, gpu=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert "--reinstall" in tool_step.command


def test_tool_install_no_desktop_extra_gpu_nvidia() -> None:
    """[desktop] must not appear even when GPU is configured."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag="cu130", book_tools_gpu=True)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert not any("[desktop]" in token for token in tool_step.command)


# ---------------------------------------------------------------------------
# plan_steps — shortcut step uses --install-desktop-shortcut
# ---------------------------------------------------------------------------


def test_shortcut_step_uses_install_desktop_shortcut_flag() -> None:
    """shortcut step command must use '--install-desktop-shortcut' (not '--install-shortcut')."""
    steps = plan_steps(has_uv=True, gpu=None)
    shortcut_step = next(s for s in steps if s.id == "shortcut")
    assert isinstance(shortcut_step.command, str)
    assert "--install-desktop-shortcut" in shortcut_step.command
    assert "--install-shortcut" not in shortcut_step.command.replace("--install-desktop-shortcut", "")


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
    """uv step uses list command — built argv must NOT contain a bare '|' token."""
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
    assert len(argv) == 3


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
    """nvidia-smi present + driver >= 525 → returns 'nvidia'; CUDA flags injected into tool_install."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "535.154.05")
    result = detect_nvidia()
    assert result == "nvidia"

    # GPU flags are now consolidated into tool_install (no separate gpu_torch step).
    steps = plan_steps(has_uv=True, gpu=result, cuda_tag="cu121")
    ids = [s.id for s in steps]
    assert "tool_install" in ids
    assert "gpu_torch" not in ids
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert any("cu121" in token for token in tool_step.command)


def test_detect_nvidia_driver_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi present + driver < 525 → returns None; gpu_torch absent from plan."""
    monkeypatch.setattr("installer.install_engine._which", lambda x: x == "nvidia-smi")
    monkeypatch.setattr("installer.install_engine._query_nvidia_driver", lambda: "470.256.02")
    result = detect_nvidia()
    assert result is None

    steps = plan_steps(has_uv=True, gpu=result)
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


# ---------------------------------------------------------------------------
# cuda_tag_for — pure helper
# ---------------------------------------------------------------------------


def test_cuda_tag_for_13_0() -> None:
    """cuda_tag_for('13.0') → 'cu130'."""
    assert cuda_tag_for("13.0") == "cu130"


def test_cuda_tag_for_12_1() -> None:
    """cuda_tag_for('12.1') → 'cu121'."""
    assert cuda_tag_for("12.1") == "cu121"


def test_cuda_tag_for_12_4() -> None:
    """cuda_tag_for('12.4') → 'cu124'."""
    assert cuda_tag_for("12.4") == "cu124"


def test_cuda_tag_for_none() -> None:
    """cuda_tag_for(None) → None (no CUDA detected)."""
    assert cuda_tag_for(None) is None


def test_cuda_tag_for_garbage() -> None:
    """cuda_tag_for('garbage') → None (unparseable)."""
    assert cuda_tag_for("garbage") is None


def test_cuda_tag_for_empty() -> None:
    """cuda_tag_for('') → None."""
    assert cuda_tag_for("") is None


# ---------------------------------------------------------------------------
# _query_cuda_version — injectable seam
# ---------------------------------------------------------------------------


def test_query_cuda_version_parses_smi_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed canned nvidia-smi output with 'CUDA Version: 13.0' → '13.0'."""
    import subprocess as _subprocess

    SAMPLE_SMI = """+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 570.144.01             Driver Version: 570.144.01   CUDA Version: 13.0     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
"""

    def fake_run(*args: object, **kwargs: object) -> _subprocess.CompletedProcess[str]:  # type: ignore[type-arg]
        return _subprocess.CompletedProcess(args=[], returncode=0, stdout=SAMPLE_SMI)

    monkeypatch.setattr("installer.install_engine._subprocess_run", fake_run)
    result = _query_cuda_version()
    assert result == "13.0"


def test_query_cuda_version_returns_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """subprocess.run raises → _query_cuda_version returns None."""

    def fail_run(*args: object, **kwargs: object) -> None:
        raise OSError("nvidia-smi not found")

    monkeypatch.setattr("installer.install_engine._subprocess_run", fail_run)
    assert _query_cuda_version() is None


def test_query_cuda_version_no_cuda_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """nvidia-smi output without CUDA Version line → returns None."""
    import subprocess as _subprocess

    def fake_run(*args: object, **kwargs: object) -> _subprocess.CompletedProcess[str]:  # type: ignore[type-arg]
        return _subprocess.CompletedProcess(args=[], returncode=0, stdout="no cuda info here")

    monkeypatch.setattr("installer.install_engine._subprocess_run", fake_run)
    assert _query_cuda_version() is None


# ---------------------------------------------------------------------------
# cuda_supports_book_tools_gpu — CUDA version >= 12.4 gate
# ---------------------------------------------------------------------------


def test_cuda_supports_book_tools_gpu_13_0() -> None:
    """'13.0' → True (major > 12)."""
    assert cuda_supports_book_tools_gpu("13.0") is True


def test_cuda_supports_book_tools_gpu_12_4() -> None:
    """'12.4' → True (exactly at boundary)."""
    assert cuda_supports_book_tools_gpu("12.4") is True


def test_cuda_supports_book_tools_gpu_12_3() -> None:
    """'12.3' → False (below boundary)."""
    assert cuda_supports_book_tools_gpu("12.3") is False


def test_cuda_supports_book_tools_gpu_11_8() -> None:
    """'11.8' → False (major < 12)."""
    assert cuda_supports_book_tools_gpu("11.8") is False


def test_cuda_supports_book_tools_gpu_none() -> None:
    """None → False (no CUDA detected)."""
    assert cuda_supports_book_tools_gpu(None) is False


def test_cuda_supports_book_tools_gpu_garbage() -> None:
    """'garbage' → False (unparseable)."""
    assert cuda_supports_book_tools_gpu("garbage") is False


# ---------------------------------------------------------------------------
# plan_steps — PD_INDEX_URL always present in tool_install command
# (regression guard for the reported "No solution found" bug)
# ---------------------------------------------------------------------------


def test_tool_install_always_has_pd_index_url_gpu_none() -> None:
    """gpu=None → tool_install command contains PD_INDEX_URL (package not on PyPI)."""
    steps = plan_steps(has_uv=True, gpu=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert "--extra-index-url" in argv
    assert PD_INDEX_URL in argv


def test_tool_install_always_has_pd_index_url_nvidia_with_cuda_tag() -> None:
    """gpu='nvidia' + cuda_tag='cu130' → tool_install command still contains PD_INDEX_URL."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag="cu130")
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert "--extra-index-url" in argv
    assert PD_INDEX_URL in argv


def test_tool_install_always_has_pd_index_url_nvidia_no_cuda_tag() -> None:
    """gpu='nvidia' + cuda_tag=None (CPU fallback) → tool_install still contains PD_INDEX_URL."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert "--extra-index-url" in argv
    assert PD_INDEX_URL in argv


# ---------------------------------------------------------------------------
# plan_steps — CUDA torch index injected when gpu='nvidia' + cuda_tag set
# ---------------------------------------------------------------------------


def test_tool_install_nvidia_cuda_tag_cu130_has_pytorch_index() -> None:
    """gpu='nvidia' + cuda_tag='cu130' → --extra-index-url https://download.pytorch.org/whl/cu130."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag="cu130")
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    pytorch_url = "https://download.pytorch.org/whl/cu130"
    assert pytorch_url in argv
    idx = argv.index(pytorch_url)
    assert argv[idx - 1] == "--extra-index-url"


def test_tool_install_nvidia_no_cuda_tag_no_pytorch_index() -> None:
    """gpu='nvidia' + cuda_tag=None (CPU fallback) → NO pytorch.org index in command."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert not any("download.pytorch.org" in token for token in argv)


# ---------------------------------------------------------------------------
# plan_steps — book_tools_gpu extra
# ---------------------------------------------------------------------------


def test_tool_install_book_tools_gpu_true_adds_with_flag() -> None:
    """book_tools_gpu=True → command contains '--with' 'pdomain-book-tools[gpu]'."""
    steps = plan_steps(
        has_uv=True,
        gpu="nvidia",
        cuda_tag="cu130",
        book_tools_gpu=True,
    )
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert "--with" in argv
    idx = argv.index("--with")
    assert argv[idx + 1] == "pdomain-book-tools[gpu]"


def test_tool_install_book_tools_gpu_false_no_with_flag() -> None:
    """book_tools_gpu=False (default) → no '--with pdomain-book-tools[gpu]' in command."""
    steps = plan_steps(
        has_uv=True,
        gpu="nvidia",
        cuda_tag="cu130",
        book_tools_gpu=False,
    )
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    argv = tool_step.command
    assert "pdomain-book-tools[gpu]" not in argv


# ---------------------------------------------------------------------------
# plan_steps — no gpu_torch step anymore
# ---------------------------------------------------------------------------


def test_no_gpu_torch_step_exists() -> None:
    """gpu_torch step must NOT appear in plan — it was the broken no-op pattern."""
    for gpu_val, cuda_val in [
        (None, None),
        ("nvidia", "cu130"),
        ("nvidia", None),
    ]:
        steps = plan_steps(has_uv=True, gpu=gpu_val, cuda_tag=cuda_val)
        ids = [s.id for s in steps]
        assert "gpu_torch" not in ids, (
            f"gpu_torch step found for gpu={gpu_val!r}, cuda_tag={cuda_val!r}: {ids}"
        )


# ---------------------------------------------------------------------------
# plan_steps — cuda_tag parameter
# ---------------------------------------------------------------------------


def test_plan_steps_nvidia_cuda_tag_cu130_in_tool_install() -> None:
    """gpu='nvidia' + cuda_tag='cu130' → tool_install command contains cu130 pytorch URL."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag="cu130")
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert any("cu130" in token for token in tool_step.command)
    assert any("download.pytorch.org/whl/cu130" in token for token in tool_step.command)


def test_plan_steps_nvidia_cuda_tag_cu121_in_tool_install() -> None:
    """gpu='nvidia' + cuda_tag='cu121' → tool_install command contains cu121 pytorch URL."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag="cu121")
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert any("download.pytorch.org/whl/cu121" in token for token in tool_step.command)


def test_plan_steps_nvidia_no_cuda_tag_tool_install_no_pytorch() -> None:
    """gpu='nvidia' + cuda_tag=None → tool_install has no pytorch.org URL (CPU fallback)."""
    steps = plan_steps(has_uv=True, gpu="nvidia", cuda_tag=None)
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert not any("download.pytorch.org" in token for token in tool_step.command)


def test_plan_steps_no_gpu_tool_install_no_pytorch() -> None:
    """gpu=None → tool_install has no pytorch.org URL."""
    steps = plan_steps(has_uv=True, gpu=None, cuda_tag="cu130")
    tool_step = next(s for s in steps if s.id == "tool_install")
    assert isinstance(tool_step.command, list)
    assert not any("download.pytorch.org" in token for token in tool_step.command)


def test_display_command_joins_list_argv() -> None:
    """List-form commands render as a readable shell string, not a list repr."""
    rendered = display_command(
        ["uv", "tool", "install", "pdomain-ocr-simple-gui", "--extra-index-url", "https://x/"]
    )
    assert rendered.startswith("uv tool install ")
    assert "[" not in rendered.split(" ", 3)[0]  # no raw "['uv', ..." list repr
    assert "--extra-index-url https://x/" in rendered


def test_display_command_passes_string_through() -> None:
    """String commands are returned unchanged."""
    assert display_command("uv tool install foo") == "uv tool install foo"


def test_display_command_renders_in_plan(capsys: pytest.CaptureFixture[str]) -> None:
    """The printed plan shows a shell string for list-form commands."""
    steps = [Step(id="t", description="d", command=["uv", "tool", "install", "x"], needs_sudo=False)]
    run(steps, assume_yes=False, dry_run=True)
    out = capsys.readouterr().out
    assert "uv tool install" in out
    assert "['uv'" not in out  # the raw list repr must not appear
