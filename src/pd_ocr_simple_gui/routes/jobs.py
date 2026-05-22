"""Jobs routes — POST/GET/LIST/DELETE /api/jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pd_ocr_simple_gui.models import AppPrefs, PageResult, ProjectSpec, ProjectStatus
from pd_ocr_simple_gui.pipeline import collect_images, run_project
from pd_ocr_simple_gui.storage import (
    delete_project,
    list_projects,
    read_project,
    write_project,
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


async def _pipeline_run_job(spec: ProjectSpec) -> None:
    """Background task: run OCR pipeline for the given project spec."""
    from pd_ocr_ops.gpu import LocalStageDispatcher

    from pd_ocr_simple_gui.app import get_dispatcher

    dispatcher = get_dispatcher()
    if dispatcher is None:
        # Fallback: create a bare dispatcher if lifespan hasn't run
        dispatcher = LocalStageDispatcher()

    async def _status_callback(status: ProjectStatus) -> None:
        pass  # Status is already persisted by run_project; callback is a hook for future SSE

    try:
        # Seed initial page list from collected images
        images = await collect_images(spec.source_path)
        init_pages = [
            PageResult(page_idx=i, page_name=img.name, state="queued") for i, img in enumerate(images)
        ]
        init_status = ProjectStatus(
            project_id=spec.project_id,
            state="queued" if images else "succeeded",
            page_count=len(images),
            pages_done=0,
            pages=init_pages,
        )
        write_project(spec, init_status)

        if not images:
            done_status = ProjectStatus(
                project_id=spec.project_id,
                state="succeeded",
                page_count=0,
                pages_done=0,
                pages=[],
            )
            write_project(spec, done_status)
            return

        await run_project(spec, dispatcher, _status_callback)

    except Exception:  # noqa: BLE001  # background job failure must be recorded, not propagated
        try:
            _, current = read_project(spec.project_id)
            err_status = ProjectStatus(
                project_id=spec.project_id,
                state="failed",
                page_count=current.page_count,
                pages_done=current.pages_done,
                pages=current.pages,
            )
            write_project(spec, err_status)
        except Exception:  # noqa: BLE001, S110  # best-effort failed-status write; nothing left to do if it fails
            pass


@router.post("", status_code=202, response_model=dict[str, str])
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
    background_tasks.add_task(_pipeline_run_job, spec)
    return {"project_id": project_id}


@router.get("", response_model=list[ProjectStatus])
async def list_jobs() -> list[ProjectStatus]:
    """Return all projects as a list of ProjectStatus enriched with name and output_dir."""
    projects = list_projects()
    return [
        status.model_copy(update={"name": spec.name, "output_dir": spec.output_dir})
        for spec, status in projects
    ]


@router.get("/{project_id}", response_model=ProjectStatus)
async def get_job(project_id: str) -> ProjectStatus:
    """Return ProjectStatus enriched with name and output_dir from ProjectSpec."""
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return status.model_copy(update={"name": spec.name, "output_dir": spec.output_dir})


@router.delete("/{project_id}", response_class=Response)
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


@router.post("/{project_id}/rerun", status_code=202, response_model=dict[str, str])
async def rerun_job(project_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Reset all pages to queued and re-run the full project pipeline."""
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    # Reset all pages to queued
    reset_pages = [
        PageResult(
            page_idx=page.page_idx,
            page_name=page.page_name,
            state="queued",
        )
        for page in status.pages
    ]
    reset_status = ProjectStatus(
        project_id=project_id,
        state="queued",
        page_count=status.page_count,
        pages_done=0,
        pages=reset_pages,
    )
    write_project(spec, reset_status)

    # Re-enqueue the pipeline
    background_tasks.add_task(_pipeline_run_job, spec)
    return {"project_id": project_id, "state": "queued"}


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
    except Exception:  # noqa: BLE001, S110  # recent-projects prefs update is best-effort
        pass
