"""Pages routes — GET/PUT/POST /api/pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
    """Return the page sidecar JSON for the given page."""
    try:
        spec, _ = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    try:
        return read_page_sidecar(spec, page_idx)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Page not found") from exc


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
async def rerun_page(project_id: str, page_idx: int) -> None:
    """Re-run OCR on a single page — stub until M2."""
    raise HTTPException(status_code=501, detail="Rerun not yet implemented (M2)")
