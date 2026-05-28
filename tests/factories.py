"""Test factories for pdomain-ocr-simple-gui models."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import write_project


def make_project_spec(
    project_id: str = "test-proj-id-001",
    name: str = "Test Project",
    source_path: str = "/tmp/source",
    output_dir: str = "/tmp/output",
    engine: str = "doctr",
    language: str = "en",
    created_at: datetime | None = None,
    last_opened_at: datetime | None = None,
    **kwargs: object,
) -> ProjectSpec:
    """Return a minimal valid ProjectSpec with sensible defaults."""
    return ProjectSpec(
        project_id=project_id,
        name=name,
        source_path=source_path,
        output_dir=output_dir,
        engine=engine,  # type: ignore[arg-type]
        language=language,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=last_opened_at or datetime(2026, 1, 2, tzinfo=UTC),
        **kwargs,
    )


def make_page_result(
    page_idx: int = 0,
    page_name: str = "page_001.png",
    state: str = "succeeded",
    text_preview: str = "",
    error: str | None = None,
) -> PageResult:
    """Return a minimal valid PageResult with sensible defaults."""
    return PageResult(
        page_idx=page_idx,
        page_name=page_name,
        state=state,  # type: ignore[arg-type]
        text_preview=text_preview,
        error=error,
    )


def write_seeded_project(
    tmp_path: Path,
    project_id: str = "test-proj-id-001",
    name: str = "Test Project",
    pages: list[PageResult] | None = None,
    state: str = "succeeded",
) -> tuple[ProjectSpec, ProjectStatus]:
    """Write a seeded project to the storage root and return (spec, status).

    Requires ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT`` to already be set in the
    environment (e.g. via the ``projects_root`` fixture).
    """
    if pages is None:
        pages = [
            make_page_result(page_idx=0, page_name="page_001.png", state="succeeded"),
            make_page_result(page_idx=1, page_name="page_002.png", state="succeeded"),
        ]
    spec = make_project_spec(
        project_id=project_id,
        name=name,
        source_path=str(tmp_path / "source"),
        output_dir=str(tmp_path / "output"),
    )
    status = ProjectStatus(
        project_id=project_id,
        state=state,  # type: ignore[arg-type]
        page_count=len(pages),
        pages_done=sum(1 for p in pages if p.state == "succeeded"),
        pages=pages,
    )
    write_project(spec, status)
    return spec, status
