# src/pdomain_ocr_simple_gui/routes/config.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from pdomain_ocr_simple_gui.runtime.container_detect import detect_containerized
from pdomain_ocr_simple_gui.runtime.mode import read_mode
from pdomain_ocr_simple_gui.runtime.ocr_engines import detect_ocr_engines

router = APIRouter()


class ConfigResponse(BaseModel):
    """Response model for GET /api/config."""

    mode: str
    is_containerized: bool
    detected_device: str
    gpu_available: bool
    ocr_engines: list[dict[str, object]]


def _detect_device() -> str:
    """Return the auto-detected dispatch device ("local"/"mps"/"cpu").

    Best-effort: pdomain-ops owns detection. Defaults to "cpu" if the
    helper is unavailable for any reason.
    """
    try:
        from pdomain_ops.gpu.device import pick_device

        return pick_device()
    except (ImportError, ValueError, RuntimeError):
        return "cpu"


@router.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return runtime mode, container flag, and detected GPU/CPU device."""
    device = _detect_device()
    return ConfigResponse(
        mode=read_mode().value,
        is_containerized=detect_containerized(),
        detected_device=device,
        gpu_available=device != "cpu",
        ocr_engines=detect_ocr_engines(),
    )
