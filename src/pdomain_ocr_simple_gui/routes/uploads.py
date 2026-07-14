# src/pdomain_ocr_simple_gui/routes/uploads.py
"""POST /api/uploads — multipart file upload with size cap and zip auto-extraction."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from pdomain_ocr_simple_gui.auth import require_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowlist for upload_id path components: uuid hex plus an optional
# ``upload-`` prefix. Bans dots, slashes, and percent-encoded traversal.
_UPLOAD_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_DEFAULT_ROOT = Path.home() / ".local/share/pdomain-ocr-simple-gui/uploads"
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


def _max_extracted_bytes() -> int:
    """Return the cap on total decompressed bytes for a single zip extraction.

    Defaults to the compressed-bytes cap (``_max_bytes()``) when unset, so a
    zip whose declared uncompressed size wildly exceeds its upload size (a
    zip bomb) is rejected before any entry is written to disk.
    """
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_EXTRACTED_BYTES")
    if raw is not None:
        return int(raw)
    return _max_bytes()


class UploadResponse(BaseModel):
    """Response body for a successful upload."""

    upload_id: str


@router.post("/api/uploads", response_model=UploadResponse, dependencies=[Depends(require_token)])
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
                    _ = tmp.write(chunk)
                tmp_path = Path(tmp.name)
            _ = tmp_path.rename(target)
            if target.suffix.lower() == ".zip":
                # Extraction is CPU/IO-bound synchronous work — run it off the
                # event loop so one large zip doesn't stall other requests.
                await asyncio.to_thread(_extract_in_place, target)
        return UploadResponse(upload_id=upload_id)
    except HTTPException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception:  # cleanup staging dir on unexpected error
        logger.exception(
            "Unexpected error during file upload; cleaning up staging directory",
            extra={"context": f"upload_id={upload_id!r}, staging={staging!r}"},
        )
        shutil.rmtree(staging, ignore_errors=True)
        raise


@router.delete("/api/uploads/{upload_id}", response_class=Response, dependencies=[Depends(require_token)])
async def delete_upload(upload_id: str) -> Response:
    """Delete the staging directory for *upload_id*.

    Called when the user clears a chosen upload on the home page so orphan
    staging dirs do not accumulate (B-HOME-004). Accepts both the bare-hex
    form (``root/<id>``, what the upload route writes) and the canonical
    ``root/upload-<id>`` form. Returns 200 when a dir was removed, 204 when
    nothing matched (idempotent), and 400 for a traversal-unsafe id.
    """
    if not _UPLOAD_ID_RE.fullmatch(upload_id):
        raise HTTPException(status_code=400, detail="invalid upload_id")

    root = _upload_root()
    removed = False
    for candidate in (root / upload_id, root / f"upload-{upload_id}"):
        # Containment guard: the resolved path must stay under the root.
        resolved = candidate.resolve()
        if not str(resolved).startswith(str(root.resolve()) + "/"):
            raise HTTPException(status_code=400, detail="invalid upload_id")
        if resolved.is_dir():
            shutil.rmtree(resolved)
            removed = True
    if not removed:
        return Response(status_code=204)
    return Response(status_code=200, content='{"status": "deleted"}', media_type="application/json")


def _extract_in_place(zip_path: Path) -> None:
    """Extract a zip file into its parent directory, then remove the zip.

    Raises HTTPException(400) if any entry would escape the parent directory
    (traversal guard), and HTTPException(413) if the total decompressed size
    exceeds ``_max_extracted_bytes()`` (zip-bomb guard) — checked before any
    entry is written to disk. Runs synchronously; callers on the event loop
    must dispatch via ``asyncio.to_thread``.
    """
    extract_to = zip_path.parent
    with zipfile.ZipFile(zip_path) as zf:
        total = sum(info.file_size for info in zf.infolist())
        if total > _max_extracted_bytes():
            raise HTTPException(status_code=413, detail="zip expands beyond extraction cap")
        for info in zf.infolist():
            target = (extract_to / info.filename).resolve()
            if not str(target).startswith(str(extract_to.resolve()) + "/"):
                raise HTTPException(status_code=400, detail="zip traversal blocked")
        zf.extractall(extract_to)
    zip_path.unlink()
