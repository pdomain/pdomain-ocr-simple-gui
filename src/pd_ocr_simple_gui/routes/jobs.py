"""Jobs routes — POST/GET/LIST/DELETE /api/jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pd_ocr_simple_gui.models import AppPrefs, PageResult, ProjectSpec, ProjectStatus
from pd_ocr_simple_gui.storage import (
    delete_project,
    list_projects,
    read_project,
    write_combined_txt,
    write_project,
    write_txt,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    """Request body for POST /api/jobs."""

    name: str
    source_path: str
    output_dir: str
    engine: Literal["doctr", "tesseract"] = "doctr"
    language: str = "en"
    save_json: bool = False
    combined_txt: bool = True


def _stub_run_job(project_id: str) -> None:
    """Background stub: immediately marks job done with one fake page."""
    try:
        spec, status = read_project(project_id)
        # Mark all pages done
        done_pages = [
            PageResult(page_idx=p.page_idx, page_name=p.page_name, state="done", text_preview="[stub]")
            for p in status.pages
        ]
        done_status = ProjectStatus(
            project_id=project_id,
            state="done",
            page_count=status.page_count,
            pages_done=len(done_pages),
            pages=done_pages,
        )
        write_project(spec, done_status)
        for page in done_pages:
            write_txt(spec, page.page_idx, "[stub OCR output]")
        if spec.combined_txt:
            write_combined_txt(spec, done_status)
    except Exception:  # noqa: BLE001, S110
        pass


@router.post("")
async def create_job(body: CreateJobRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Create a new OCR project and enqueue it."""
    project_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    spec = ProjectSpec(
        project_id=project_id,
        name=body.name,
        source_path=body.source_path,
        output_dir=body.output_dir,
        engine=body.engine,
        language=body.language,
        save_json=body.save_json,
        combined_txt=body.combined_txt,
        created_at=now,
        last_opened_at=now,
    )
    status = ProjectStatus(
        project_id=project_id,
        state="queued",
        page_count=0,
        pages_done=0,
        pages=[],
    )
    write_project(spec, status)
    background_tasks.add_task(_stub_run_job, project_id)
    return {"project_id": project_id}


@router.get("")
async def list_jobs() -> list[dict[str, Any]]:
    """Return all projects as a list of ProjectStatus dicts."""
    projects = list_projects()
    return [status.model_dump() for _, status in projects]


@router.get("/{project_id}")
async def get_job(project_id: str) -> dict[str, Any]:
    """Return ProjectStatus for the given project_id."""
    try:
        _, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return status.model_dump()


@router.delete("/{project_id}")
async def delete_job(project_id: str) -> Response:
    """Delete a project. Returns 200 if it existed, 204 if it didn't."""
    from pd_ocr_simple_gui.storage import get_project_dir

    proj_dir = get_project_dir(project_id)
    if not proj_dir.exists():
        return Response(status_code=204)
    # Remove from recent_projects in prefs (best-effort)
    _remove_from_recent_projects(project_id)
    delete_project(project_id)
    return Response(status_code=200, content='{"status": "deleted"}', media_type="application/json")


def _remove_from_recent_projects(project_id: str) -> None:
    """Remove project_id from prefs recent_projects (best-effort, no-op on error)."""
    try:
        from pd_ocr_simple_gui.app import get_prefs_adapter

        adapter = get_prefs_adapter()
        if adapter is None:
            return
        raw = adapter.read().apps.get("pd-ocr-simple-gui", {})
        prefs = AppPrefs.model_validate(raw) if raw else AppPrefs()
        prefs.recent_projects = [p for p in prefs.recent_projects if p.get("project_id") != project_id]
        adapter.write_app("pd-ocr-simple-gui", prefs.model_dump())
    except Exception:  # noqa: BLE001, S110
        pass
