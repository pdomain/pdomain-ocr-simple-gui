# src/pd_ocr_simple_gui/routes/uploads.py
"""POST /api/uploads — multipart file upload with size cap and zip auto-extraction."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()

_DEFAULT_ROOT = Path.home() / ".local/share/pd-ocr-simple-gui/uploads"
_DEFAULT_MAX_BYTES = 2 * 1024**3  # 2 GiB total per request
_DEFAULT_MAX_FILES = 5000


def _upload_root() -> Path:
    """Return (and create) the staging root directory for uploads."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT")
    root = Path(raw) if raw else _DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _max_bytes() -> int:
    """Return the per-request upload size cap in bytes."""
    return int(os.environ.get("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_BYTES", _DEFAULT_MAX_BYTES))


def _max_files() -> int:
    """Return the per-request file count cap."""
    return int(os.environ.get("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_FILES", _DEFAULT_MAX_FILES))


class UploadResponse(BaseModel):
    """Response body for a successful upload."""

    upload_id: str


@router.post("/api/uploads", response_model=UploadResponse)
async def post_upload(files: list[UploadFile]) -> UploadResponse:
    """Accept multipart file uploads and stream them into a staging directory.

    Returns an upload_id that can be passed to POST /api/jobs as upload_id.
    Zip files are automatically extracted in place. A 413 is returned if the
    total bytes or file count exceed configured caps.
    """
    if not files:
        raise HTTPException(status_code=400, detail="no files supplied")
    if len(files) > _max_files():
        raise HTTPException(status_code=413, detail="too many files")

    upload_id = uuid.uuid4().hex
    staging = _upload_root() / upload_id
    staging.mkdir(parents=True)
    total = 0
    max_total = _max_bytes()
    try:
        for upload in files:
            name = Path(upload.filename or "unnamed").name  # strip path traversal
            target = staging / name
            with tempfile.NamedTemporaryFile(delete=False, dir=staging) as tmp:
                while chunk := await upload.read(64 * 1024):
                    total += len(chunk)
                    if total > max_total:
                        raise HTTPException(status_code=413, detail="upload exceeds size cap")
                    tmp.write(chunk)
                tmp_path = Path(tmp.name)
            tmp_path.rename(target)
            if target.suffix.lower() == ".zip":
                _extract_in_place(target)
        return UploadResponse(upload_id=upload_id)
    except HTTPException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception:  # cleanup staging dir on unexpected error
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _extract_in_place(zip_path: Path) -> None:
    """Extract a zip file into its parent directory, then remove the zip.

    Raises HTTPException(400) if any entry would escape the parent directory
    (traversal guard).
    """
    extract_to = zip_path.parent
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = (extract_to / info.filename).resolve()
            if not str(target).startswith(str(extract_to.resolve()) + "/"):
                raise HTTPException(status_code=400, detail="zip traversal blocked")
        zf.extractall(extract_to)
    zip_path.unlink()
