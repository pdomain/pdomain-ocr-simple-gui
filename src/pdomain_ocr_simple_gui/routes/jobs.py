"""Jobs routes — POST/GET/LIST/DELETE /api/jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.models import AppPrefs, PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.output.config import OutputConfig, OutputConfigError, resolve_output_dir
from pdomain_ocr_simple_gui.pipeline import collect_images, run_project
from pdomain_ocr_simple_gui.runtime.mode import Mode, read_mode
from pdomain_ocr_simple_gui.runtime.ocr_engines import (
    is_engine_request_available,
    resolve_engine_language,
)
from pdomain_ocr_simple_gui.sources import SourceError
from pdomain_ocr_simple_gui.sources.local_path import LocalPathSource
from pdomain_ocr_simple_gui.sources.uploaded_files import UploadedFilesSource
from pdomain_ocr_simple_gui.statecharts.job_lifecycle import InvalidJobTransition, assert_job_transition
from pdomain_ocr_simple_gui.storage import (
    delete_project,
    list_projects,
    read_project,
    validate_project_id,
    write_project,
    write_text_atomic,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_APP_ID = "pdomain-ocr-simple-gui"

# ---------------------------------------------------------------------------
# Concurrent-jobs semaphore
# ---------------------------------------------------------------------------

_DEFAULT_MAX_CONCURRENT_JOBS = 3


def _max_concurrent_jobs() -> int:
    """Return the configured max concurrent jobs (PDOMAIN_MAX_CONCURRENT_JOBS, default 3)."""
    raw = os.environ.get("PDOMAIN_MAX_CONCURRENT_JOBS", "")
    try:
        return int(raw) if raw else _DEFAULT_MAX_CONCURRENT_JOBS
    except ValueError:
        return _DEFAULT_MAX_CONCURRENT_JOBS


# Module-level semaphore — monkeypatch target for tests.
_job_semaphore: asyncio.Semaphore = asyncio.Semaphore(_max_concurrent_jobs())

_DEFAULT_OUTPUT_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/outputs"
_DEFAULT_UPLOAD_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/uploads"
_DEFAULT_JOBS_META_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/jobs"
ApiJobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]


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
    # Atomic publish — _read_job_meta_output_mode swallows parse errors, so a
    # torn truncate-in-place write would silently degrade to mode=None.
    write_text_atomic(meta_dir / "output_mode.json", json.dumps({"mode": output_mode}))


def _read_job_meta_output_mode(job_id: str) -> str | None:
    """Read the persisted output_mode for job_id, returning None if absent."""
    meta_file = _jobs_meta_root() / job_id / "output_mode.json"
    if not meta_file.exists():
        return None
    try:
        data = cast("object", json.loads(meta_file.read_text(encoding="utf-8")))
        if isinstance(data, dict):
            typed_data = cast("dict[str, object]", data)
            mode = typed_data.get("mode")
            if mode is not None:
                return str(mode)
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
    # NOTE: no save_json / combined_txt knob — sidecars + combined.txt are
    # always written (B-HOME-011 cleanup). A stale save_json/combined_txt in a
    # POST body is simply ignored (extra fields ignored by default).
    # Post-OCR text normalization toggles (mirrors pdomain-ocr-cli flags)
    straight_quotes: bool = True
    em_dash_to_double_hyphen: bool = True
    # Reorganize-page knob (illustration block emission)
    emit_illustration_placeholders: bool = False
    # Device choice: "auto" (detection), "cpu", or "gpu".
    device: Literal["auto", "cpu", "gpu"] = "auto"
    # Pages per batch; None/absent = use default (8).
    batch_pages: int | None = None


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
    from pdomain_ops.gpu import LocalStageDispatcher

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
        _, current_status = read_project(spec.project_id)
        seed_state: ApiJobState = current_status.state
        seed_error: str | None = None
        if not images:
            seed_state = cast("ApiJobState", assert_job_transition(current_status.state, "fail"))
            seed_error = (
                "No supported image files found in source; supported types are "
                "PNG, JPEG, TIFF, JPEG 2000, WebP."
            )
        init_pages = [
            PageResult(page_idx=i, page_name=img.name, state="queued") for i, img in enumerate(images)
        ]
        init_status = ProjectStatus(
            project_id=spec.project_id,
            state=seed_state,
            page_count=len(images),
            pages_done=0,
            pages=init_pages,
            error=seed_error,
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

        await run_project(spec, dispatcher, _status_callback)

    except Exception as exc:  # background job failure must be recorded, not propagated
        logger.exception(
            "Background OCR job failed; attempting to record failed status",
            extra={"context": f"project_id={spec.project_id!r}"},
        )
        try:
            _, current = read_project(spec.project_id)
            failed_state = (
                current.state
                if current.state == "failed"
                else cast("ApiJobState", assert_job_transition(current.state, "fail"))
            )
            err_status = ProjectStatus(
                project_id=spec.project_id,
                state=failed_state,
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


async def _pipeline_run_job_with_semaphore(spec: ProjectSpec) -> None:
    """Background task wrapper: run OCR then release the concurrent-jobs semaphore."""
    try:
        await _pipeline_run_job(spec)
    finally:
        _job_semaphore.release()


@router.post("", status_code=202, response_model=dict[str, str], dependencies=[Depends(require_token)])
async def create_job(body: CreateJobRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Create a new OCR project and enqueue it.

    Accepts either source_path (local mode) or upload_id. Output destination
    is controlled by the output field (OutputConfig); when absent, output_dir
    is used directly for backward compatibility.
    """
    # Check concurrent-jobs cap before doing any work.
    # In asyncio (single-threaded), checking _value then acquiring is
    # race-free — no other coroutine can preempt between two sync statements.
    if _job_semaphore._value <= 0:  # asyncio.Semaphore internal; safe in single-threaded async
        raise HTTPException(status_code=429, detail="Too many concurrent jobs; try again later")
    _ = await _job_semaphore.acquire()

    # Release the semaphore if any validation error prevents us from enqueuing.
    try:
        mode = read_mode()
        project_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        engine_available, engine_reason = is_engine_request_available(
            body.engine,
            body.language,
        )
        if not engine_available:
            raise HTTPException(status_code=400, detail=f"engine: {engine_reason}")
        resolved_language = resolve_engine_language(body.engine, body.language)

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
            language=resolved_language,
            straight_quotes=body.straight_quotes,
            em_dash_to_double_hyphen=body.em_dash_to_double_hyphen,
            emit_illustration_placeholders=body.emit_illustration_placeholders,
            device=body.device,
            batch_pages=body.batch_pages,
            created_at=now,
            last_opened_at=now,
        )
        queued_state = cast("ApiJobState", assert_job_transition("new", "queue"))
        status = ProjectStatus(
            project_id=project_id,
            state=queued_state,
            page_count=0,
            pages_done=0,
            pages=[],
        )
        write_project(spec, status)
        await _add_to_recent_projects(spec, status)
        background_tasks.add_task(_pipeline_run_job_with_semaphore, spec)
    except Exception:
        # Release the slot we acquired — the job will not run.
        _job_semaphore.release()
        raise
    return {"project_id": project_id}


@router.get("", response_model=list[ProjectStatus], dependencies=[Depends(require_token)])
async def list_jobs() -> list[ProjectStatus]:
    """Return all projects as a list of ProjectStatus enriched with name and output_dir."""
    projects = list_projects()
    return [
        status.model_copy(update={"name": spec.name, "output_dir": spec.output_dir})
        for spec, status in projects
    ]


@router.get("/{project_id}", response_model=ProjectStatus, dependencies=[Depends(require_token)])
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


def _delete_job_meta(job_id: str) -> None:
    """Remove the per-job meta sidecar dir (<JOBS_META_ROOT>/<id>/). Best-effort.

    Without this, deleting a job left the output_mode sidecar orphaned
    (B-RESULTS-014).
    """
    import shutil

    meta_dir = _jobs_meta_root() / job_id
    if meta_dir.exists():
        shutil.rmtree(meta_dir, ignore_errors=True)


def _delete_output_mirror(output_dir: str) -> None:
    """Remove the user-visible output mirror dir (spec.output_dir). Best-effort.

    The mirror is what ``GET /api/jobs/{id}/download`` streams; leaving it
    behind on delete meant a deleted job's ZIP was still downloadable
    (B-RESULTS-014). Guarded so we never rmtree an empty/unset path or one
    outside the managed output root unintentionally.
    """
    import shutil

    if not output_dir:
        return
    mirror = Path(output_dir)
    # Only remove a directory that exists; a stray file path is left alone.
    if mirror.is_dir():
        shutil.rmtree(mirror, ignore_errors=True)


@router.delete("/{project_id}", response_class=Response, dependencies=[Depends(require_token)])
async def delete_job(project_id: str) -> Response:
    """Delete a project. Returns 200 if it existed, 204 if it didn't.

    Removes ALL on-disk artifacts for the job: the canonical project dir, the
    user-visible output mirror (spec.output_dir), and the per-job meta sidecar
    (<JOBS_META_ROOT>/<id>/). Previously only the canonical dir was removed,
    leaving the mirror + meta orphaned so a deleted job's ZIP still downloaded
    (B-RESULTS-014). ResultsPage has no delete control; the shared AppShell jobs
    dock owns the current delete affordance (docs/context/intent-map.md).
    """
    from pdomain_ocr_simple_gui.storage import get_project_dir

    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    proj_dir = get_project_dir(project_id)
    if not proj_dir.exists():
        return Response(status_code=204)

    # Read the spec (for output_dir) BEFORE rmtree removes project.json.
    output_dir = ""
    try:
        spec, _ = read_project(project_id)
        output_dir = spec.output_dir
    except FileNotFoundError:
        # No readable spec — canonical dir exists but project.json is gone;
        # we can still remove the canonical dir + meta below.
        logger.warning(
            "delete_job: project dir present but project.json unreadable; output mirror cannot be located",
            extra={"context": f"project_id={project_id!r}"},
        )

    # Remove from recent_projects in prefs (best-effort)
    await _remove_from_recent_projects(project_id)
    delete_project(project_id)
    _delete_output_mirror(output_dir)
    _delete_job_meta(project_id)
    return Response(status_code=200, content='{"status": "deleted"}', media_type="application/json")


@router.post(
    "/{project_id}/rerun",
    status_code=202,
    response_model=dict[str, str],
    dependencies=[Depends(require_token)],
)
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
    try:
        reset_state = cast("ApiJobState", assert_job_transition(status.state, "rerun_requested"))
    except InvalidJobTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Check concurrent-jobs cap before mutating any stored state — see
    # create_job's comment on why the check-then-acquire is race-free here.
    if _job_semaphore._value <= 0:  # asyncio.Semaphore internal; safe in single-threaded async
        raise HTTPException(status_code=429, detail="Too many concurrent jobs; try again later")
    _ = await _job_semaphore.acquire()

    try:
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
            state=reset_state,
            page_count=status.page_count,
            pages_done=0,
            pages=reset_pages,
        )
        write_project(spec, reset_status)

        # Re-enqueue the pipeline
        background_tasks.add_task(_pipeline_run_job_with_semaphore, spec)
    except Exception:
        # Release the slot we acquired — the job will not run.
        _job_semaphore.release()
        raise
    return {"project_id": project_id, "state": reset_state}


async def _remove_from_recent_projects(project_id: str) -> None:
    """Remove project_id from prefs recent_projects (best-effort, no-op on error).

    Uses asyncio.to_thread for the blocking filelock operations so the
    asyncio event loop is not stalled while the prefs lock is held.
    """
    try:
        from pdomain_ocr_simple_gui.app import get_prefs_adapter

        adapter = get_prefs_adapter()
        if adapter is None:
            return
        prefs_data = await asyncio.to_thread(adapter.read)
        raw = prefs_data.apps.get(_APP_ID, {})
        prefs = AppPrefs.model_validate(raw) if raw else AppPrefs()
        prefs.recent_projects = [p for p in prefs.recent_projects if p.get("project_id") != project_id]
        await asyncio.to_thread(adapter.write_app, _APP_ID, prefs.model_dump())
    except Exception:  # recent-projects prefs update is best-effort
        logger.exception(
            "Failed to remove project from recent-projects prefs",
            extra={"context": f"project_id={project_id!r}"},
        )


async def _add_to_recent_projects(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Add a created project to prefs recent_projects (best-effort, no-op on error).

    Uses asyncio.to_thread for the blocking filelock operations so the
    asyncio event loop is not stalled while the prefs lock is held.
    """
    try:
        from pdomain_ocr_simple_gui.app import get_prefs_adapter

        adapter = get_prefs_adapter()
        if adapter is None:
            return

        prefs_data = await asyncio.to_thread(adapter.read)
        raw = prefs_data.apps.get(_APP_ID, {})
        prefs = AppPrefs.model_validate(raw) if raw else AppPrefs()
        entry: dict[str, object] = {
            "project_id": spec.project_id,
            "name": spec.name,
            "source_path": spec.source_path,
            "output_dir": spec.output_dir,
            "last_opened_at": spec.last_opened_at.isoformat(),
            "page_count": status.page_count,
            "engine": spec.engine,
            "status": status.state,
        }
        prefs.recent_projects = [
            entry,
            *[
                project
                for project in prefs.recent_projects
                if project.get("project_id") != spec.project_id
                and project.get("source_path") != spec.source_path
            ],
        ][:10]
        await asyncio.to_thread(adapter.write_app, _APP_ID, prefs.model_dump())
    except Exception:  # recent-projects prefs update is best-effort
        logger.exception(
            "Failed to add project to recent-projects prefs",
            extra={"context": f"project_id={spec.project_id!r}"},
        )
