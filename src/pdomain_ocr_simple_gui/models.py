"""Pydantic models for pdomain-ocr-simple-gui."""

from __future__ import annotations

# TC002/TC003 suppressed: these are runtime imports — Pydantic needs the
# concrete types at runtime for field introspection, not type-checking only.
from datetime import datetime  # noqa: TC003
from typing import Literal

from pdomain_ops.suite.types import (
    CommonUIPrefs,  # noqa: TC002  # pyright: ignore[reportMissingTypeStubs]
)
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
    straight_quotes: bool = True
    em_dash_to_double_hyphen: bool = True
    emit_illustration_placeholders: bool = False
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
    output_mode: str | None = None
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    page_count: int
    pages_done: int
    pages: list[PageResult]
    error: str | None = None


class PageResponse(BaseModel):
    """Structured page data returned by GET /api/pages/{project_id}/{page_idx}."""

    page_idx: int
    page_name: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    text: str = ""
    width: int = 800
    height: int = 1200


class AppPrefs(BaseModel):
    """Application-level preferences for pdomain-ocr-simple-gui."""

    default_engine: str = "doctr"
    default_language: str = "en"
    default_output_dir: str = ""
    save_json_default: bool = False
    combined_txt_default: bool = True
    recent_projects: list[dict[str, object]] = []
    ui_prefs: CommonUIPrefs | None = None
