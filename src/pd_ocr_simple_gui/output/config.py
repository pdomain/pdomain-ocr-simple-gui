"""OutputConfig model and output directory resolver."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003  # Pydantic introspects Path at runtime for field validation
from typing import Literal

from pydantic import BaseModel

from pd_ocr_simple_gui.runtime.mode import Mode


class OutputConfigError(Exception):
    """Raised when an OutputConfig cannot be resolved."""


class OutputConfig(BaseModel):
    """Configuration for where OCR output files should land."""

    mode: Literal["next_to_source", "specified", "managed"]
    path: Path | None = None


def resolve_output_dir(
    cfg: OutputConfig,
    *,
    mode: Mode,
    source_dir: Path,
    managed_root: Path,
    job_id: str,
    source_is_folder: bool,
) -> Path:
    """Resolve the output directory from an OutputConfig.

    Returns the absolute Path where OCR output files should be written.
    Raises OutputConfigError if the configuration is invalid for the current
    deployment mode or source type.
    """
    if cfg.mode == "next_to_source":
        if not source_is_folder:
            raise OutputConfigError("next_to_source requires a folder source")
        return source_dir
    if cfg.mode == "specified":
        if mode is Mode.MANAGED:
            raise OutputConfigError("specified output is not allowed in managed mode")
        if cfg.path is None:
            raise OutputConfigError("specified output requires a path")
        cfg.path.mkdir(parents=True, exist_ok=True)
        return cfg.path
    # managed
    target = managed_root / job_id
    target.mkdir(parents=True, exist_ok=True)
    return target
