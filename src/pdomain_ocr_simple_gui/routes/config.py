# src/pdomain_ocr_simple_gui/routes/config.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from pdomain_ocr_simple_gui.runtime.container_detect import detect_containerized
from pdomain_ocr_simple_gui.runtime.mode import read_mode

router = APIRouter()


class ConfigResponse(BaseModel):
    """Response model for GET /api/config."""

    mode: str
    is_containerized: bool


@router.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return runtime mode and container detection flag."""
    return ConfigResponse(
        mode=read_mode().value,
        is_containerized=detect_containerized(),
    )
