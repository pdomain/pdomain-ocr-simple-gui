"""Pydantic models for pd-ocr-simple-gui."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any, Literal

from pydantic import BaseModel


class ProjectSpec(BaseModel):
    """Specification for an OCR project."""

    project_id: str
    name: str
    source_path: str
    output_dir: str
    engine: Literal["doctr", "tesseract"]
    language: str
    save_json: bool = False
    combined_txt: bool = True
    created_at: datetime
    last_opened_at: datetime


class PageResult(BaseModel):
    """Result for a single page in a project."""

    page_idx: int
    page_name: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    text_preview: str = ""
    error: str | None = None


class ProjectStatus(BaseModel):
    """Aggregated status for a project."""

    project_id: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    page_count: int
    pages_done: int
    pages: list[PageResult]


class AppPrefs(BaseModel):
    """Application-level preferences for pd-ocr-simple-gui."""

    default_engine: str = "doctr"
    default_language: str = "en"
    default_output_dir: str = ""
    save_json_default: bool = False
    combined_txt_default: bool = True
    recent_projects: list[dict[str, Any]] = []
