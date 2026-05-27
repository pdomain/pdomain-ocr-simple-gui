"""Jobs routes — POST/GET/LIST/DELETE /api/jobs."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pdomain_ocr_simple_gui.models import AppPrefs, PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.output.config import OutputConfig, OutputConfigError, resolve_output_dir
from pdomain_ocr_simple_gui.pipeline import collect_images, run_project
from pdomain_ocr_simple_gui.runtime.mode import Mode, read_mode
from pdomain_ocr_simple_gui.sources import SourceError
from pdomain_ocr_simple_gui.sources.local_path import LocalPathSource
from pdomain_ocr_simple_gui.sources.uploaded_files import UploadedFilesSource
from pdomain_ocr_simple_gui.storage import (
    delete_project,
    list_projects,
    read_project,
    validate_project_id,
    write_project,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_DEFAULT_OUTPUT_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/outputs"
_DEFAULT_UPLOAD_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/uploads"
_DEFAULT_JOBS_META_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/jobs"


def _jobs_meta_root() -> Path:
    """Return the root for per-job sidecar metadata files (PD_OCR_SIMPLE_GUI_JOBS_META_ROOT)."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT")
    root = Path(raw) if raw else _DEFAULT_JOBS_META_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_job_meta(job_id: str, output_mode: str) -> None:
    """Persist a small output_mode sidecar JSON for job_id."""
    meta_dir = _jobs_meta_root() / job_id
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "output_mode.json").write_text(json.dumps({"mode": output_mode}), encoding="utf-8")


def _read_job_meta_output_mode(job_id: str) -> str | None:
    """Read the persisted output_mode for job_id, returning None if absent."""
    meta_file = _jobs_meta_root() / job_id / "output_mode.json"
    if not meta_file.exists():
        return None
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return str(data["mode"])
    except Exception:  # sidecar read is best-effort; pass is intentional
        logger.exception(
            "Failed to read output_mode sidecar; returning None",
            extra={"context": f"meta_file={meta_file!r}"},
        )
    return None


def _managed_output_root() -> Path:
    """Return the server-managed output root directory (PD_OCR_SIMPLE_GUI_OUTPUT_ROOT)."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT")
    root = Path(raw) if raw else _DEFAULT_OUTPUT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _upload_root() -> Path:
    """Return the upload staging root directory (PD_OCR_SIMPLE_GUI_UPLOAD_ROOT)."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT")
    root = Path(raw) if raw else _DEFAULT_UPLOAD_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


class CreateJobRequest(BaseModel):
    """Request body for POST /api/jobs.

    Accepts either source_path (local-mode folder/image/zip) or upload_id
    (from POST /api/uploads). At least one must be provided.

    The output field controls where OCR results land. When omitted, output_dir
    is used directly (legacy behaviour preserved for backward compatibility).
    """

    name: str = ""
    # Source — one of:
    source_path: str = ""
    upload_id: str = ""
    # Output location — optional; when absent, output_dir is used directly.
    output_dir: str = ""
    output: OutputConfig | None = None
    # Job options:
    engine: Literal["doctr", "tesseract"] = "doctr"
    language: str = "en"
    save_json: bool = False
    combined_txt: bool = True


def _build_source_and_flags(body: CreateJobRequest, mode: Mode) -> tuple[str, bool]:
    """Resolve the source directory and source_is_folder flag.

    Returns (source_dir_str, source_is_folder).
    Raises HTTPException on invalid combinations.
    """
    if body.upload_id:
        try:
            src = UploadedFilesSource(body.upload_id, root=_upload_root())
            materialized = src.materialize()
        except SourceError as exc:
            raise HTTPException(status_code=400, detail=f"source: {exc}") from exc
        # Uploads are never "next to source" folders
        return str(materialized), False

    if not body.source_path:
        raise HTTPException(status_code=400, detail="must supply source_path or upload_id")
    if mode is Mode.MANAGED:
        raise HTTPException(status_code=400, detail="source_path is local-mode only")

    path = Path(body.source_path)
    try:
        src = LocalPathSource(path)
        materialized = src.materialize()
    except SourceError as exc:
        raise HTTPException(status_code=400, detail=f"source: {exc}") from exc
    return str(materialized), path.is_dir()


async def _pipeline_run_job(spec: ProjectSpec) -> None:
    """Background task: run OCR pipeline for the given project spec."""
    from pdomain_ops.gpu import LocalStageDispatcher  # pyright: ignore[reportMissingTypeStubs]

    from pdomain_ocr_simple_gui.app import get_dispatcher

    dispatcher = get_dispatcher()
    if dispatcher is None:
        # Fallback: create a bare dispatcher if lifespan hasn't run
        dispatcher = LocalStageDispatcher()

    async def _status_callback(status: ProjectStatus) -> None:
        _ = status
        pass  # Status is already persisted by run_project; callback is a hook for future SSE

    try:
        # Seed initial page list from collected images
        images = await collect_images(spec.source_path)
        init_pages = [
            PageResult(page_idx=i, page_name=img.name, state="queued") for i, img in enumerate(images)
        ]
        init_status = ProjectStatus(
            project_id=spec.project_id,
            state="queued" if images else "failed",
            page_count=len(images),
            pages_done=0,
            pages=init_pages,
            error=(
                None
                if images
                else (
                    "No supported image files found in source; supported types are "
                    "PNG, JPEG, TIFF, JPEG 2000, WebP."
                )
            ),
        )
        write_project(spec, init_status)

        if not images:
            # Loud failure — silently writing "succeeded" with zero pages hid real bugs
            # (e.g., dropped JPEG 2000 input) from the user.
            logger.warning(
                "Job has zero supported image files; marking failed",
                extra={"context": f"project_id={spec.project_id!r}, source={spec.source_path!r}"},
            )
            return

        await run_project(spec, dispatcher, _status_callback)  # pyright: ignore[reportArgumentType]  # LocalStageDispatcher lacks stubs

    except Exception as exc:  # background job failure must be recorded, not propagated
        logger.exception(
            "Background OCR job failed; attempting to record failed status",
            extra={"context": f"project_id={spec.project_id!r}"},
        )
        try:
            _, current = read_project(spec.project_id)
            err_status = ProjectStatus(
                project_id=spec.project_id,
                state="failed",
                page_count=current.page_count,
                pages_done=current.pages_done,
                pages=current.pages,
                error=str(exc),
            )
            write_project(spec, err_status)
        except Exception:  # best-effort failed-status write; nothing left to do if it fails
            logger.exception(
                "Could not write failed status after job error; project may be stuck in-progress",
                extra={"context": f"project_id={spec.project_id!r}"},
            )


@router.post("", status_code=202, response_model=dict[str, str])
async def create_job(body: CreateJobRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Create a new OCR project and enqueue it.

    Accepts either source_path (local mode) or upload_id. Output destination
    is controlled by the output field (OutputConfig); when absent, output_dir
    is used directly for backward compatibility.
    """
    mode = read_mode()
    project_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    if body.output is not None:
        # New path: resolve source via Source adapter, then resolve output via OutputConfig.
        source_dir_str, source_is_folder = _build_source_and_flags(body, mode)
        try:
            output_path = resolve_output_dir(
                body.output,
                mode=mode,
                source_dir=Path(source_dir_str),
                managed_root=_managed_output_root(),
                job_id=project_id,
                source_is_folder=source_is_folder,
            )
        except OutputConfigError as exc:
            raise HTTPException(status_code=400, detail=f"output: {exc}") from exc
        resolved_output_dir = str(output_path)
        resolved_source_path = source_dir_str
        _write_job_meta(project_id, body.output.mode)
    else:
        # Legacy path: source_path and output_dir are used as-is.
        resolved_source_path = body.source_path
        resolved_output_dir = body.output_dir

    spec = ProjectSpec(
        project_id=project_id,
        name=body.name,
        source_path=resolved_source_path,
        output_dir=resolved_output_dir,
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
    """Return ProjectStatus enriched with name, output_dir, and output_mode from sidecar."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    output_mode = _read_job_meta_output_mode(project_id)
    update: dict[str, object] = {"name": spec.name, "output_dir": spec.output_dir}
    if output_mode is not None:
        update["output_mode"] = output_mode
    return status.model_copy(update=update)


@router.delete("/{project_id}", response_class=Response)
async def delete_job(project_id: str) -> Response:
    """Delete a project. Returns 200 if it existed, 204 if it didn't."""
    from pdomain_ocr_simple_gui.storage import get_project_dir

    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        from pdomain_ocr_simple_gui.app import get_prefs_adapter

        adapter = get_prefs_adapter()
        if adapter is None:
            return
        raw = adapter.read().apps.get("pdomain-ocr-simple-gui", {})
        prefs = AppPrefs.model_validate(raw) if raw else AppPrefs()
        prefs.recent_projects = [p for p in prefs.recent_projects if p.get("project_id") != project_id]
        adapter.write_app("pdomain-ocr-simple-gui", prefs.model_dump())
    except Exception:  # recent-projects prefs update is best-effort
        logger.exception(
            "Failed to remove project from recent-projects prefs",
            extra={"context": f"project_id={project_id!r}"},
        )
