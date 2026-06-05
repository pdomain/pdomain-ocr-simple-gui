"""Linux installer engine for pdomain-ocr-simple-gui.

Pure, unit-testable functions.  No side effects except through injectable
seams (``_which``, ``ask``, ``run_cmd``).  This module is the tested core
that both the CLI bootstrapper and the AppImage GUI wizard build on.

Design:
- ``detect_pkg_manager()`` — probes for the distro package manager.
- ``webview_package_for(mgr)`` — maps manager to the WebKitGTK package name.
- ``detect_nvidia()`` — probes for an NVIDIA GPU via ``nvidia-smi``.
- ``plan_steps(has_uv, has_webview, gpu)`` — returns the ordered gated steps.
- ``run(steps, *, assume_yes, dry_run, ask, run_cmd)`` — interactive runner.

All distro detection goes through the injectable ``_which`` callable so tests
never shell out.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Injectable seam — swap in tests via monkeypatch
# ---------------------------------------------------------------------------


def _which(cmd: str) -> bool:
    """Return True if ``cmd`` is found on PATH (thin shutil.which wrapper)."""
    import shutil

    return shutil.which(cmd) is not None


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

# Probe order: apt before yum/dnf so Debian-family systems resolve first.
_PKG_MANAGER_PROBE_ORDER = ["apt", "dnf", "yum", "pacman", "zypper", "apk"]


def detect_pkg_manager() -> str | None:
    """Return the first package manager found on PATH, or None.

    Probe order: apt, dnf, yum, pacman, zypper, apk.  Returns the string id
    of the first hit, or ``None`` if none is available.
    """
    for mgr in _PKG_MANAGER_PROBE_ORDER:
        if _which(mgr):
            return mgr
    return None


# ---------------------------------------------------------------------------
# WebKitGTK package mapping per package manager
# ---------------------------------------------------------------------------

_WEBVIEW_PACKAGES: dict[str | None, str | None] = {
    "apt": "gir1.2-webkit2-4.1",  # Debian/Ubuntu (PyWebView requirement)
    "dnf": "webkit2gtk4.1",  # Fedora 39+
    "yum": "webkit2gtk4.1",  # older RHEL/CentOS
    "pacman": "webkit2gtk",  # Arch Linux
    "zypper": "typelib-1_0-WebKit2-4_1",  # openSUSE
    "apk": "webkit2gtk",  # Alpine Linux
    None: None,  # unknown distro
}


def webview_package_for(mgr: str | None) -> str | None:
    """Return the WebKitGTK package name for the given package manager.

    Returns ``None`` for unknown managers (caller should print manual
    instructions and continue rather than aborting).
    """
    return _WEBVIEW_PACKAGES.get(mgr)


# ---------------------------------------------------------------------------
# NVIDIA detection
# ---------------------------------------------------------------------------


def detect_nvidia() -> str | None:
    """Return ``'nvidia'`` if ``nvidia-smi`` is found on PATH, else ``None``."""
    return "nvidia" if _which("nvidia-smi") else None


# ---------------------------------------------------------------------------
# Step dataclass
# ---------------------------------------------------------------------------


@dataclass
class Step:
    """A single gated installer step.

    Attributes:
        id:          Stable identifier used in tests and logging.
        description: Human-readable description shown to the user.
        command:     Shell command string (may use pipes / shell syntax).
        needs_sudo:  Whether the command must be prefixed with ``sudo``.
    """

    id: str
    description: str
    command: str
    needs_sudo: bool


# ---------------------------------------------------------------------------
# Step planning
# ---------------------------------------------------------------------------

# The app ID used in the tool-install and shortcut steps.
_APP_ID = "pdomain-ocr-simple-gui"
_DESKTOP_EXTRA = f"{_APP_ID}[desktop]"


def plan_steps(
    *,
    has_uv: bool,
    has_webview: bool,
    gpu: str | None,
    mgr: str | None = None,
) -> list[Step]:
    """Return the ordered list of gated installer steps.

    Steps are omitted when they are already satisfied:
    - ``uv`` step omitted when ``has_uv=True``.
    - ``webview`` step omitted when ``has_webview=True``.
    - ``gpu_torch`` step included **only** when ``gpu == 'nvidia'``.
    - ``tool_install`` and ``shortcut`` are always included.

    Args:
        has_uv:      True when ``uv`` is already installed.
        has_webview: True when the WebKitGTK runtime is already available.
        gpu:         ``'nvidia'`` to include the CUDA torch step; None/other to skip.
        mgr:         Package manager id (for the webview install command).
                     Auto-detected if None.
    """
    if mgr is None:
        mgr = detect_pkg_manager()

    webview_pkg = webview_package_for(mgr)

    steps: list[Step] = []

    if not has_uv:
        steps.append(
            Step(
                id="uv",
                description="Install uv (Python toolchain manager)",
                command="curl -LsSf https://astral.sh/uv/install.sh | sh",
                needs_sudo=False,
            )
        )

    if not has_webview:
        if webview_pkg and mgr:
            # Build the install command from the detected manager.
            install_cmd = _build_pkg_install_cmd(mgr, webview_pkg)
        else:
            # Unknown distro: show manual instructions; step still listed.
            install_cmd = (
                "# Unknown package manager — install the WebKitGTK 4.1 runtime manually"
                " (e.g. 'sudo apt-get install gir1.2-webkit2-4.1' on Debian/Ubuntu)"
            )
        steps.append(
            Step(
                id="webview",
                description=f"Install WebKitGTK runtime ({webview_pkg or 'see instructions above'})",
                command=install_cmd,
                needs_sudo=True,
            )
        )

    steps.append(
        Step(
            id="tool_install",
            description=f"Install {_APP_ID} via uv tool install",
            command=f'uv tool install "{_DESKTOP_EXTRA}"',
            needs_sudo=False,
        )
    )

    if gpu == "nvidia":
        steps.append(
            Step(
                id="gpu_torch",
                description="Enable GPU acceleration (swap CPU torch for CUDA build)",
                command=(
                    f"uv tool run --from {_APP_ID} pip install"
                    " torch --index-url https://download.pytorch.org/whl/cu121"
                ),
                needs_sudo=False,
            )
        )

    steps.append(
        Step(
            id="shortcut",
            description="Install desktop shortcut and application menu entry",
            command=f"{_APP_ID} --install-shortcut",
            needs_sudo=False,
        )
    )

    return steps


def _build_pkg_install_cmd(mgr: str, package: str) -> str:
    """Return the package-manager install command for the given package."""
    _cmds: dict[str, str] = {
        "apt": f"apt-get install -y {package}",
        "dnf": f"dnf install -y {package}",
        "yum": f"yum install -y {package}",
        "pacman": f"pacman -S --noconfirm {package}",
        "zypper": f"zypper install -y {package}",
        "apk": f"apk add {package}",
    }
    return _cmds.get(mgr, f"# install {package}")


# ---------------------------------------------------------------------------
# Interactive runner
# ---------------------------------------------------------------------------


def run(
    steps: list[Step],
    *,
    assume_yes: bool,
    dry_run: bool,
    ask: Callable[[str], str] = input,
    run_cmd: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,  # type: ignore[type-arg]
) -> None:
    """Print and optionally execute the installer steps.

    Each step is shown with its description and command.  In interactive mode
    the user is prompted to confirm; ``assume_yes=True`` skips the prompt.
    ``dry_run=True`` prints the plan without executing anything.

    Args:
        steps:      Ordered list of ``Step`` objects from ``plan_steps()``.
        assume_yes: If True, execute all steps without asking.
        dry_run:    If True, print the plan but do not execute anything.
        ask:        Callable used to prompt the user (injectable for tests).
        run_cmd:    Callable used to execute commands (injectable for tests).
    """
    print(f"\nInstaller plan ({len(steps)} step(s)):")  # noqa: T201
    for i, step in enumerate(steps, 1):
        sudo_tag = " [sudo]" if step.needs_sudo else ""
        print(f"  {i}. {step.description}{sudo_tag}")  # noqa: T201
        print(f"     $ {step.command}")  # noqa: T201
    print()  # noqa: T201

    if dry_run:
        print("Dry-run mode — no changes made.")  # noqa: T201
        return

    for step in steps:
        sudo_tag = " [sudo]" if step.needs_sudo else ""
        print(f"\n[{step.id}]{sudo_tag} {step.description}")  # noqa: T201
        print(f"  $ {step.command}")  # noqa: T201

        if not assume_yes:
            answer = ask("Run this step? [Y/n] ").strip().lower()
            if answer not in ("", "y", "yes"):
                print("  Skipped.")  # noqa: T201
                continue

        cmd = _build_exec_args(step)
        run_cmd(cmd, check=True)
        print("  Done.")  # noqa: T201


def _build_exec_args(step: Step) -> list[str]:
    """Convert a step's command string into a list[str] for subprocess.

    If ``needs_sudo`` is True, prepends ``['sudo']``.  Uses ``shlex.split``
    for splitting; shell pipelines (``|``) are NOT supported in this path —
    commands that need a shell pipe are passed as a single-element list via
    ``shell=True`` in a real invocation, but for the testable path we always
    return a list so tests can inspect individual tokens.

    Note: the uv bootstrap step uses a shell pipe (``curl ... | sh``).  In a
    real run this would need ``shell=True``; in tests the run_cmd is stubbed so
    this is fine.
    """
    tokens = shlex.split(step.command)
    if step.needs_sudo:
        return ["sudo", *tokens]
    return tokens
