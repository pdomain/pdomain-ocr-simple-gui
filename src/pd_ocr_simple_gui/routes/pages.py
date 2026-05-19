"""Pages routes — GET/PUT/POST /api/pages."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pd_ocr_simple_gui.models import PageResponse
from pd_ocr_simple_gui.pipeline import run_project
from pd_ocr_simple_gui.storage import (
    read_page_sidecar,
    read_project,
    write_page_sidecar,
    write_txt,
)

router = APIRouter(prefix="/api/pages", tags=["pages"])


class SaveTextRequest(BaseModel):
    """Request body for PUT /api/pages/{project_id}/{page_idx}/text."""

    text: str


@router.get("/{project_id}/{page_idx}")
async def get_page(project_id: str, page_idx: int) -> dict[str, Any]:
    """Return structured PageResponse for the given page."""
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    # Resolve page metadata from status
    page_entry = next((p for p in status.pages if p.page_idx == page_idx), None)
    if page_entry is None:
        raise HTTPException(status_code=404, detail="Page not found")

    # Read sidecar for text/dimensions (best-effort)
    sidecar: dict[str, Any] = {}
    with contextlib.suppress(FileNotFoundError):
        sidecar = read_page_sidecar(spec, page_idx)

    text = sidecar.get("edited_text") or sidecar.get("text") or ""
    width = int(sidecar.get("width", 800))
    height = int(sidecar.get("height", 1200))

    response = PageResponse(
        page_idx=page_idx,
        page_name=page_entry.page_name,
        state=page_entry.state,
        text=text,
        width=width,
        height=height,
    )
    return response.model_dump()


@router.get("/{project_id}/{page_idx}/image")
async def get_page_image(project_id: str, page_idx: int) -> FileResponse:
    """Stream the source image file for the given page."""
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    # Resolve page_name from status
    page_name: str | None = None
    for page in status.pages:
        if page.page_idx == page_idx:
            page_name = page.page_name
            break
    if page_name is None:
        raise HTTPException(status_code=404, detail="Page not found")
    # Look for image in source_path
    source_dir = Path(spec.source_path)
    image_path = source_dir / page_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(str(image_path))


@router.put("/{project_id}/{page_idx}/text")
async def put_page_text(project_id: str, page_idx: int, body: SaveTextRequest) -> dict[str, str]:
    """Save edited text for the given page."""
    try:
        spec, _ = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    sidecar: dict[str, Any]
    try:
        sidecar = read_page_sidecar(spec, page_idx)
    except FileNotFoundError:
        sidecar = {"page_idx": page_idx}
    sidecar["edited_text"] = body.text
    write_page_sidecar(spec, page_idx, sidecar)
    write_txt(spec, page_idx, body.text)
    return {"status": "saved"}


@router.post("/{project_id}/{page_idx}/rerun")
async def rerun_page(project_id: str, page_idx: int) -> dict[str, Any]:
    """Re-run OCR on a single page and return the updated PageResult.

    Uses a single-page spec by temporarily pointing source_path at the
    image file, so run_project processes exactly one image.
    """
    from pd_ocr_ops.gpu import LocalStageDispatcher

    from pd_ocr_simple_gui.app import get_dispatcher

    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    # Resolve the page's image path
    page_entry = next((p for p in status.pages if p.page_idx == page_idx), None)
    if page_entry is None:
        raise HTTPException(status_code=404, detail="Page not found")

    source_dir = Path(spec.source_path)
    image_path = source_dir / page_entry.page_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    dispatcher = get_dispatcher()
    if dispatcher is None:
        dispatcher = LocalStageDispatcher()

    # Run single-image OCR: reuse run_project with source_path pointing at
    # the single image file (collect_images accepts a file path).
    single_image_spec = spec.model_copy(update={"source_path": str(image_path)})

    # Temporarily set the page to queued so run_project can update it
    from pd_ocr_simple_gui.models import PageResult, ProjectStatus
    from pd_ocr_simple_gui.storage import update_page_result

    queued_page = PageResult(
        page_idx=page_idx,
        page_name=page_entry.page_name,
        state="queued",
    )
    update_page_result(spec, queued_page)

    result_holder: list[ProjectStatus] = []

    async def _cb(s: ProjectStatus) -> None:
        result_holder.append(s)

    await run_project(single_image_spec, dispatcher, _cb)

    # The run_project call used single_image_spec (idx 0), but our project
    # has the page at page_idx. Re-read the actual project page state.
    _, updated_status = read_project(project_id)
    updated_page = next((p for p in updated_status.pages if p.page_idx == page_idx), page_entry)
    return updated_page.model_dump()
