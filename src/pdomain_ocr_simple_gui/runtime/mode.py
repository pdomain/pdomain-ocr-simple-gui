# src/pdomain_ocr_simple_gui/runtime/mode.py
from __future__ import annotations

import os
from enum import StrEnum


class Mode(StrEnum):
    """Runtime operating mode controlling source and output affordances."""

    LOCAL = "local"
    MANAGED = "managed"


_ENV_VAR = "PD_OCR_SIMPLE_GUI_MODE"


def read_mode() -> Mode:
    """Read the runtime mode from the environment, defaulting to LOCAL."""
    raw = os.environ.get(_ENV_VAR, Mode.LOCAL.value).lower()
    try:
        return Mode(raw)
    except ValueError as exc:
        raise RuntimeError(f"{_ENV_VAR} must be one of {[m.value for m in Mode]}, got {raw!r}") from exc
