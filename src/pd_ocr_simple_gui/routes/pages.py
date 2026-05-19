"""Pages routes — GET/PUT/POST /api/pages."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pd_ocr_simple_gui.models import PageResponse, PageResult
from pd_ocr_simple_gui.pipeline import extract_text
from pd_ocr_simple_gui.storage import (
    read_page_sidecar,
    read_project,
    update_page_result,
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
    # Look for image in source_path.
    # When source_path is a single file, use it directly; otherwise join with page_name.
    source = Path(spec.source_path)
    if source.is_file():
        # Sanity-check: the stored page_name must match the actual filename
        if page_name != source.name:
            raise HTTPException(status_code=404, detail="Image file not found")
        image_path = source
    else:
        image_path = source / page_name
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

    Runs OCR inline (does NOT call run_project) so that the correct page_idx
    is always updated and page 0 is never corrupted.  Awaits the async
    dispatcher directly — non-blocking, yields control to the event loop.
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

    # Resolve the actual image file (handles both file and directory source_path)
    source = Path(spec.source_path)
    image_path = source if source.is_file() else source / page_entry.page_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    dispatcher = get_dispatcher()
    if dispatcher is None:
        dispatcher = LocalStageDispatcher()

    # Mark this page as running
    running_page = PageResult(
        page_idx=page_idx,
        page_name=page_entry.page_name,
        state="running",
    )
    update_page_result(spec, running_page)

    page_id = f"{spec.project_id}/{page_idx}"

    try:
        # Await the async stage dispatcher — non-blocking, yields control to the event loop
        stage_result = await dispatcher.run_stage(
            "ocr",
            page_id,
            image_path=str(image_path),
            engine=spec.engine,
            language=spec.language,
        )
        pages_list: list[dict[str, Any]] = stage_result.metadata.get("pages", [])
        page_dict: dict[str, Any] = pages_list[0] if pages_list else {}
        text = extract_text(page_dict)

        # Augment the sidecar with the extracted text so GET /api/pages can surface it
        sidecar_data: dict[str, Any] = {**page_dict, "text": text}
        write_page_sidecar(spec, page_idx, sidecar_data)
        write_txt(spec, page_idx, text)

        done_page = PageResult(
            page_idx=page_idx,
            page_name=page_entry.page_name,
            state="succeeded",
            text_preview=text[:60],
        )
    except Exception as exc:  # noqa: BLE001
        done_page = PageResult(
            page_idx=page_idx,
            page_name=page_entry.page_name,
            state="failed",
            error=str(exc),
        )

    update_page_result(spec, done_page)
    return done_page.model_dump()
