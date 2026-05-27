"""Download endpoint — streams a job's output directory as a zip archive.

Supports filtering by content type via ``?include=`` query param:
- ``text`` — only ``.txt`` files (plus any image files present)
- ``json`` — only ``.json`` files (plus any image files present)
- ``text,json`` / ``text+json`` (default) — both text and JSON, plus images

Image files are always included regardless of filter, preserving the legacy
zip contents. The choice of text-vs-JSON has moved from job-creation time to
download time — see ``CreateJobRequest`` for the deprecated flags.
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from pdomain_ocr_simple_gui.storage import read_project, validate_project_id

router = APIRouter()


def _output_root() -> Path:
    """Return the managed output root, defaulting to ~/.local/share/pdomain-ocr-simple-gui/outputs."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT")
    if raw:
        return Path(raw)
    return Path.home() / ".local/share/pdomain-ocr-simple-gui/outputs"


_VALID_INCLUDE_TOKENS = frozenset({"text", "json"})


def _parse_include(value: str) -> set[str]:
    """Parse the include query param into a set of {"text", "json"}.

    Accepts comma-separated, plus-separated, or single-token forms. Raises
    HTTPException(400) on unknown tokens.
    """
    # Normalize: + arrives URL-decoded as a space; treat both as separators
    # alongside the canonical comma form.
    normalized = value.replace("+", ",").replace(" ", ",")
    raw_tokens = [t.strip() for t in normalized.split(",") if t.strip()]
    if not raw_tokens:
        raise HTTPException(
            status_code=400,
            detail="include must be one of: text, json, text+json (or text,json)",
        )
    tokens = set(raw_tokens)
    unknown = tokens - _VALID_INCLUDE_TOKENS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"include has unknown token(s) {sorted(unknown)!r}; must be one of: text, json, text+json"
            ),
        )
    return tokens


def _resolve_job_output_dir(job_id: str) -> Path | None:
    """Return the resolved output directory for job_id, or None if not found.

    Prefers spec.output_dir from the stored project, falling back to the
    managed outputs root for backwards compatibility with jobs created before
    output_dir was always populated.
    """
    try:
        validate_project_id(job_id)
    except ValueError:
        return None
    try:
        spec, _ = read_project(job_id)
    except FileNotFoundError:
        # Legacy fallback: maybe output exists in the managed root only.
        legacy = _output_root() / job_id
        return legacy if legacy.is_dir() else None
    candidate = Path(spec.output_dir) if spec.output_dir else None
    if candidate is not None and candidate.is_dir():
        return candidate
    legacy = _output_root() / job_id
    return legacy if legacy.is_dir() else None


def _should_include(path: Path, tokens: set[str]) -> bool:
    """Decide whether *path* belongs in the zip given the include tokens."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return "text" in tokens
    if suffix == ".json":
        return "json" in tokens
    # Non-text/JSON files (images, etc.) are always included to preserve
    # legacy behaviour — the previous endpoint zipped everything in the dir.
    return True


@router.get("/api/jobs/{job_id}/download")
def download_job(
    job_id: str,
    include: str = Query(
        "text,json",
        description="Comma- or plus-separated list of {text, json}. Default: text,json.",
    ),
) -> StreamingResponse:
    """Stream the job's output directory as a zip attachment.

    Returns 404 when the job output directory does not exist, 400 when the
    ``include`` query parameter is malformed.
    """
    tokens = _parse_include(include)

    job_dir = _resolve_job_output_dir(job_id)
    if job_dir is None:
        raise HTTPException(status_code=404, detail="job output not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(job_dir.rglob("*")):
            if not path.is_file():
                continue
            if not _should_include(path, tokens):
                continue
            zf.write(path, arcname=path.relative_to(job_dir))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}.zip"',
        },
    )
