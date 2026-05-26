"""Download endpoint — streams a job's output directory as a zip archive."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()


def _output_root() -> Path:
    """Return the managed output root, defaulting to ~/.local/share/pd-ocr-simple-gui/outputs."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT")
    if raw:
        return Path(raw)
    return Path.home() / ".local/share/pd-ocr-simple-gui/outputs"


@router.get("/api/jobs/{job_id}/download")
def download_job(job_id: str) -> StreamingResponse:
    """Stream the job's output directory as a zip attachment.

    Returns 404 when the job output directory does not exist.
    """
    job_dir = _output_root() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="job output not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(job_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(job_dir))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}.zip"',
        },
    )
