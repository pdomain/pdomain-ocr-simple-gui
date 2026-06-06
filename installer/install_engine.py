"""Linux installer engine for pdomain-ocr-simple-gui.

Pure, unit-testable functions.  No side effects except through injectable
seams (``_which``, ``ask``, ``run_cmd``, ``_query_nvidia_driver``).  This
module is the tested core that both the CLI bootstrapper and the AppImage GUI
wizard build on.

Design:
- ``detect_pkg_manager()`` — probes for the distro package manager.
- ``webview_package_for(mgr)`` — maps manager to the Qt xcb-cursor system
  package name.  The Qt backend (PyQt6 + PyQt6-WebEngine) is bundled in the
  tool venv via ``pdomain-ocr-simple-gui[desktop]`` → ``pdomain-ops[desktop]``
  and requires no system package.  The *only* system package needed is the
  xcb-cursor lib, and only on X11 (Wayland sessions need nothing).
- ``detect_nvidia()`` — probes for an NVIDIA GPU via ``nvidia-smi`` and
  validates the driver version against ``_MIN_DRIVER_VERSION``.
- ``plan_steps(has_uv, has_webview, gpu)`` — returns the ordered gated steps.
- ``run(steps, *, assume_yes, dry_run, ask, run_cmd)`` — interactive runner.

All distro detection goes through the injectable ``_which`` callable so tests
never shell out.  NVIDIA driver version queries go through
``_query_nvidia_driver`` so tests never invoke ``nvidia-smi``.
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


def _query_nvidia_driver() -> str | None:
    """Return the NVIDIA driver version string, or None on any error.

    Calls ``nvidia-smi --query-gpu=driver_version --format=csv,noheader``.
    Injectable seam — replace in tests via monkeypatch so tests never
    actually invoke ``nvidia-smi``.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


# Minimum NVIDIA driver version that supports CUDA 12 (cu121 wheel ABI).
# Spec §7.3: offer gpu_torch only when driver >= this threshold.
_MIN_DRIVER_VERSION = 525


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
# Qt xcb-cursor package mapping per package manager
#
# The desktop webview backend is Qt (PyQt6 + PyQt6-WebEngine).  Those wheels
# are self-contained and ship inside the tool venv — they arrive automatically
# via the [desktop] extra chain and need no system package.
#
# The ONLY system package needed is the Qt xcb-cursor plugin, required only on
# X11 (XCB platform).  Wayland sessions ($WAYLAND_DISPLAY set, no $DISPLAY)
# use the Wayland QPA and need nothing.
# ---------------------------------------------------------------------------

_WEBVIEW_PACKAGES: dict[str | None, str | None] = {
    "apt": "libxcb-cursor0",  # Debian/Ubuntu
    "dnf": "xcb-util-cursor",  # Fedora 39+
    "yum": "xcb-util-cursor",  # older RHEL/CentOS
    "pacman": "xcb-util-cursor",  # Arch Linux
    "zypper": "libxcb-cursor0",  # openSUSE
    "apk": "xcb-util-cursor",  # Alpine Linux
    None: None,  # unknown distro
}


def webview_package_for(mgr: str | None) -> str | None:
    """Return the Qt xcb-cursor package name for the given package manager.

    The Qt backend (PyQt6 + PyQt6-WebEngine) is bundled inside the tool venv
    via the ``[desktop]`` extra — no system package is needed for Qt itself.
    The xcb-cursor lib is only required on X11; Wayland sessions need nothing.

    Returns ``None`` for unknown managers (caller should print manual
    instructions and continue rather than aborting).
    """
    return _WEBVIEW_PACKAGES.get(mgr)


# ---------------------------------------------------------------------------
# NVIDIA detection
# ---------------------------------------------------------------------------


def detect_nvidia() -> str | None:
    """Return ``'nvidia'`` if a capable NVIDIA GPU is detected, else ``None``.

    A capable GPU requires both ``nvidia-smi`` on PATH **and** a driver version
    >= ``_MIN_DRIVER_VERSION`` (525, the minimum for CUDA 12).

    If ``nvidia-smi`` is present but the driver is too old (or the version
    cannot be parsed), returns ``None`` and prints a guidance message so the
    caller's step-planner omits the ``gpu_torch`` step.  The user is directed
    to the official driver download page to upgrade.
    """
    if not _which("nvidia-smi"):
        return None

    version_str = _query_nvidia_driver()
    if version_str is None:
        # nvidia-smi present but version query failed — treat as too-old to be safe.
        print(  # noqa: T201
            "WARNING: nvidia-smi found but driver version could not be determined. "
            + "GPU acceleration step will be skipped.\n"
            + "To enable GPU support, ensure NVIDIA driver >= 525 is installed:\n"
            + "  https://www.nvidia.com/en-us/drivers/"
        )
        return None

    # Parse the major version component (e.g. "525.105.17" → 525).
    try:
        major = int(version_str.split(".")[0])
    except (ValueError, IndexError):
        print(  # noqa: T201
            f"WARNING: Could not parse NVIDIA driver version '{version_str}'. "
            + "GPU acceleration step will be skipped.\n"
            + "To enable GPU support, ensure NVIDIA driver >= 525 is installed:\n"
            + "  https://www.nvidia.com/en-us/drivers/"
        )
        return None

    if major < _MIN_DRIVER_VERSION:
        print(  # noqa: T201
            f"WARNING: NVIDIA driver version {version_str} is below the minimum "
            + f"required for CUDA 12 (driver >= {_MIN_DRIVER_VERSION}).\n"
            + "GPU acceleration step will be skipped.\n"
            + "To enable GPU support, upgrade your NVIDIA driver:\n"
            + "  Official:       https://www.nvidia.com/en-us/drivers/\n"
            + "  Ubuntu/Debian:  ubuntu-drivers devices && sudo ubuntu-drivers install\n"
            + "  Arch Linux:     pacman -S nvidia\n"
            + "  Fedora:         dnf install akmod-nvidia\n"
            + "After upgrading (and rebooting if necessary), re-run the installer."
        )
        return None

    return "nvidia"


# ---------------------------------------------------------------------------
# Step dataclass
# ---------------------------------------------------------------------------


@dataclass
class Step:
    """A single gated installer step.

    Attributes:
        id:          Stable identifier used in tests and logging.
        description: Human-readable description shown to the user.
        command:     The command to execute.  Either a ``str`` (split via
                     ``shlex.split`` at run time) or a pre-built ``list[str]``
                     argv (used when shell syntax such as ``|`` is required,
                     e.g. the ``uv`` bootstrap step passes
                     ``["sh", "-c", "curl ... | sh"]``).
        needs_sudo:  Whether the command must be prefixed with ``sudo``.
    """

    id: str
    description: str
    command: str | list[str]
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
        has_webview: True when the Qt xcb-cursor lib is already available.
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
                # Use a list argv so the shell pipe is handled by sh, not shlex.split.
                # shlex.split("curl ... | sh") would pass "|" and "sh" as literal
                # arguments to curl, which fails.  ["sh", "-c", "..."] is the
                # correct way to run a shell pipeline in subprocess.
                command=["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                needs_sudo=False,
            )
        )

    if not has_webview:
        if webview_pkg and mgr:
            # Build the install command from the detected manager.
            install_cmd = _build_pkg_install_cmd(mgr, webview_pkg)
        else:
            # Unknown distro: show manual instructions; step still listed.
            # Qt itself is bundled in the venv; only the xcb-cursor lib is system-level.
            install_cmd = (
                "# Unknown package manager — install the Qt xcb-cursor lib manually"
                " (X11 only; e.g. 'sudo apt-get install libxcb-cursor0' on Debian/Ubuntu;"
                " Wayland sessions need nothing)"
            )
        steps.append(
            Step(
                id="webview",
                description=f"Install Qt xcb-cursor lib ({webview_pkg or 'see instructions above'}) — X11 only",
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
        _ = run_cmd(cmd, check=True)
        print("  Done.")  # noqa: T201


def _build_exec_args(step: Step) -> list[str]:
    """Convert a step's command into a ``list[str]`` argv for subprocess.

    - If ``step.command`` is already a ``list[str]``, it is used as-is.
    - If ``step.command`` is a ``str``, it is split via ``shlex.split``.
      Plain string commands must NOT contain shell metacharacters (``|``,
      ``&&``, etc.) — those belong in list-form commands like
      ``["sh", "-c", "..."]``.

    If ``needs_sudo`` is True, ``["sudo"]`` is prepended to the final argv.
    """
    tokens = list(step.command) if isinstance(step.command, list) else shlex.split(step.command)
    if step.needs_sudo:
        return ["sudo", *tokens]
    return tokens
