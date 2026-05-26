# src/pdomain_ocr_simple_gui/runtime/container_detect.py
from __future__ import annotations

import os
from pathlib import Path

_DOCKERENV = Path("/.dockerenv")
_PODMAN_MARKER = Path("/run/.containerenv")
_INIT_CGROUP = Path("/proc/1/cgroup")
_CGROUP_NEEDLES = ("docker", "containerd", "kubepods")


def _read_init_cgroup() -> str:
    try:
        return _INIT_CGROUP.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_containerized() -> bool:
    """Return True when the process is running inside a container."""
    if _DOCKERENV.exists():
        return True
    if _PODMAN_MARKER.exists():
        return True
    if os.environ.get("container"):  # noqa: SIM112  # OCI runtime sets lowercase
        return True
    cgroup = _read_init_cgroup()
    return any(needle in cgroup for needle in _CGROUP_NEEDLES)
