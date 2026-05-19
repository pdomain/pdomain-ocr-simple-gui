"""Pydantic models for pd-ocr-simple-gui."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any, Literal

from pd_ocr_ops.suite.types import CommonUIPrefs  # noqa: TC002
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
    name: str = ""
    output_dir: str = ""
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    page_count: int
    pages_done: int
    pages: list[PageResult]


class PageResponse(BaseModel):
    """Structured page data returned by GET /api/pages/{project_id}/{page_idx}."""

    page_idx: int
    page_name: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    text: str = ""
    width: int = 800
    height: int = 1200


class AppPrefs(BaseModel):
    """Application-level preferences for pd-ocr-simple-gui."""

    default_engine: str = "doctr"
    default_language: str = "en"
    default_output_dir: str = ""
    save_json_default: bool = False
    combined_txt_default: bool = True
    recent_projects: list[dict[str, Any]] = []
    ui_prefs: CommonUIPrefs | None = None
