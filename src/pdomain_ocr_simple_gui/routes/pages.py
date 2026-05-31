"""Pages routes — GET/PUT/POST /api/pages."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pdomain_ocr_simple_gui.auth import require_token
from pdomain_ocr_simple_gui.models import PageResponse, PageResult, ProjectSpec
from pdomain_ocr_simple_gui.pipeline import (
    JsonObject,
    build_sidecar_payload,
    extract_text,
    first_page_dict,
    resolve_device,
)
from pdomain_ocr_simple_gui.storage import (
    read_page_sidecar,
    read_project,
    update_page_result,
    validate_project_id,
    write_page_sidecar,
    write_txt,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pages", tags=["pages"])


class SaveTextRequest(BaseModel):
    """Request body for PUT /api/pages/{project_id}/{page_idx}/text."""

    text: str


def _read_sidecar(spec: ProjectSpec, page_idx: int) -> JsonObject:
    """Best-effort JSON object reader for page sidecars."""
    with contextlib.suppress(FileNotFoundError):
        sidecar = read_page_sidecar(spec, page_idx)
        return cast("JsonObject", sidecar)
    return {}


def _json_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _json_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            return int(value)
    return default


@router.get("/{project_id}/{page_idx}", response_model=PageResponse)
async def get_page(project_id: str, page_idx: int) -> PageResponse:
    """Return structured PageResponse for the given page."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

    # Resolve page metadata from status
    page_entry = next((p for p in status.pages if p.page_idx == page_idx), None)
    if page_entry is None:
        raise HTTPException(status_code=404, detail="Page not found")

    # Read sidecar for text/dimensions (best-effort)
    sidecar = _read_sidecar(spec, page_idx)

    # edited_text takes priority when the key holds a string (including the
    # empty string — the user may have intentionally cleared the field).
    # When edited_text is absent or None, fall through to the OCR text.
    edited = _json_str(sidecar.get("edited_text"))
    text = (
        edited
        if edited is not None
        else (
            _json_str(sidecar.get("text"))
            # Older jobs (pre-build_sidecar_payload) wrote a DocTR Page.to_dict()
            # tree without a top-level "text" key.  Fall back to the page
            # text_preview baked into status.json so the editor pane isn't blank
            # while the user re-runs to refresh the sidecar.
            or page_entry.text_preview
            or ""
        )
    )
    width = _json_int(sidecar.get("width"), default=800)
    height = _json_int(sidecar.get("height"), default=1200)

    return PageResponse(
        page_idx=page_idx,
        page_name=page_entry.page_name,
        state=page_entry.state,
        text=text,
        width=width,
        height=height,
    )


def _transcode_for_browser(source: Path, fmt: str) -> Path:
    """Transcode *source* to ``fmt`` (``"WEBP"`` or ``"PNG"``) next to it.

    Cached by (basename, format); regenerated only when the source file is
    newer than the cached output.  WebP uses lossy q=80 which is fine for
    in-browser OCR viewing — the original image is preserved untouched and
    is what ends up in the output zip.
    """
    from PIL import Image

    suffix = ".webp" if fmt == "WEBP" else ".png"
    cached = source.with_name(f"{source.name}.viewer{suffix}")
    if cached.exists() and cached.stat().st_mtime >= source.stat().st_mtime:
        return cached
    with Image.open(source) as img:
        # Drop alpha for JPEG-family sources to keep WebP small; PNG keeps mode as-is.
        save_img = img
        if fmt == "WEBP":
            if save_img.mode not in ("RGB", "RGBA"):
                save_img = save_img.convert("RGB")
            save_img.save(cached, format="WEBP", quality=80)
        else:
            save_img.save(cached, format="PNG")
    return cached


def _client_accepts_webp(accept_header: str | None) -> bool:
    if not accept_header:
        return False
    return "image/webp" in accept_header.lower()


@router.get("/{project_id}/{page_idx}/image", response_class=FileResponse)
async def get_page_image(project_id: str, page_idx: int, request: Request) -> FileResponse:
    """Stream the page image, transcoded to WebP (preferred) or PNG.

    Content negotiation: if the request's ``Accept`` header lists
    ``image/webp``, the cached WebP transcode is served; otherwise PNG.
    The original source file is preserved untouched on disk — only the
    in-browser viewer sees the transcoded copy.
    """
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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

    accept_webp = _client_accepts_webp(request.headers.get("accept"))
    fmt = "WEBP" if accept_webp else "PNG"
    media_type = "image/webp" if accept_webp else "image/png"

    # If the source is already in the target format, serve it directly —
    # transcoding a PNG to PNG (or WebP to WebP) just wastes CPU and risks
    # tripping over Pillow strictness on already-valid files.
    src_suffix = image_path.suffix.lower()
    if (fmt == "PNG" and src_suffix == ".png") or (fmt == "WEBP" and src_suffix == ".webp"):
        return FileResponse(str(image_path), media_type=media_type)

    try:
        served = _transcode_for_browser(image_path, fmt)
    except Exception as exc:  # malformed image / Pillow failure — surface as 500-ish 404
        logger.exception(
            "Failed to transcode page image for browser",
            extra={"context": f"project_id={project_id!r}, page_idx={page_idx}, fmt={fmt}"},
        )
        raise HTTPException(status_code=500, detail="Image transcode failed") from exc
    return FileResponse(str(served), media_type=media_type)


@router.put(
    "/{project_id}/{page_idx}/text", response_model=dict[str, str], dependencies=[Depends(require_token)]
)
async def put_page_text(project_id: str, page_idx: int, body: SaveTextRequest) -> dict[str, str]:
    """Save edited text for the given page."""
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        spec, status = read_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    # Guard the page index BEFORE any disk write. An out-of-range index used to
    # fall through to write_page_sidecar → _page_name_for_idx, which raised an
    # uncaught FileNotFoundError surfacing as a 500 (and could leave a partial
    # write). Resolve to a clean 404 with no disk mutation instead.
    if not any(p.page_idx == page_idx for p in status.pages):
        raise HTTPException(status_code=404, detail="Page not found")
    sidecar: JsonObject = _read_sidecar(spec, page_idx)
    if not sidecar:
        sidecar = {"page_idx": page_idx}
    sidecar["edited_text"] = body.text
    write_page_sidecar(spec, page_idx, sidecar)
    write_txt(spec, page_idx, body.text)
    return {"status": "saved"}


class RerunRequest(BaseModel):
    """Optional body for POST /api/pages/{id}/{idx}/rerun."""

    engine: Literal["doctr", "tesseract"] | None = None


@router.post(
    "/{project_id}/{page_idx}/rerun", response_model=PageResult, dependencies=[Depends(require_token)]
)
async def rerun_page(
    project_id: str,
    page_idx: int,
    body: RerunRequest | None = None,
) -> PageResult:
    """Re-run OCR on a single page and return the updated PageResult.

    Runs OCR inline (does NOT call run_project) so that the correct page_idx
    is always updated and page 0 is never corrupted.  Awaits the async
    dispatcher directly — non-blocking, yields control to the event loop.
    """
    from pdomain_ops.gpu import LocalStageDispatcher  # pyright: ignore[reportMissingTypeStubs]

    from pdomain_ocr_simple_gui.app import get_dispatcher

    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        engine = body.engine if (body and body.engine) else spec.engine
        # Await the async stage dispatcher — non-blocking, yields control to the event loop
        stage_result = await dispatcher.run_stage(
            "ocr",
            page_id,
            image_path=str(image_path),
            engine=engine,
            language=spec.language,
            device=resolve_device(spec.device),
        )
        page_dict = first_page_dict(stage_result.metadata)

        # Mirror run_project's reorganize + text-normalize pipeline so the
        # rerun output matches the initial OCR run.
        raw_text = extract_text(page_dict)
        reorganized_dict: JsonObject = page_dict
        reorganized_text = ""
        try:
            from pdomain_book_tools.ocr.page import Page

            page_obj = Page.from_dict(page_dict)
            page_obj.reorganize_page(
                emit_illustration_placeholders=spec.emit_illustration_placeholders,
            )
            reorganized_dict = cast("JsonObject", page_obj.to_dict())
            reorganized_text = page_obj.text
        except Exception:
            logger.exception(
                "reorganize_page() failed on rerun; falling back to raw dict",
                extra={"context": f"page_idx={page_idx}, image={image_path.name!r}"},
            )
        if reorganized_text.strip():
            page_dict = reorganized_dict
            text = reorganized_text
        else:
            text = raw_text
        try:
            from pdomain_book_tools.ocr import (
                apply_text_normalizations,  # pyright: ignore[reportAttributeAccessIssue]
            )

            text = apply_text_normalizations(
                text,
                straight_quotes=spec.straight_quotes,
                em_dash_to_double_hyphen=spec.em_dash_to_double_hyphen,
            )
        except ImportError:
            logger.debug(
                "apply_text_normalizations unavailable; skipping rerun cleanup",
            )

        # Augment the sidecar with text + normalized words list so GET
        # /api/pages and /words can surface them without re-walking the tree.
        sidecar_data: JsonObject = build_sidecar_payload(page_dict, text)
        # Preserve the user's saved edit across a rerun. build_sidecar_payload
        # produces a fresh dict from the OCR tree (no edited_text), so a rerun
        # used to silently discard hand-edits. Carry over edited_text from the
        # prior sidecar when present (a string, including the empty string —
        # the user may have intentionally cleared the field). The refreshed OCR
        # still lands in `text` + `words`; only the edit is preserved.
        prior = _read_sidecar(spec, page_idx)
        prior_edit = _json_str(prior.get("edited_text"))
        if prior_edit is not None:
            sidecar_data["edited_text"] = prior_edit
        write_page_sidecar(spec, page_idx, sidecar_data)
        # Keep the per-page .txt consistent with what GET /api/pages surfaces:
        # edited_text wins when preserved, otherwise the refreshed OCR text.
        write_txt(spec, page_idx, prior_edit if prior_edit is not None else text)

        done_page = PageResult(
            page_idx=page_idx,
            page_name=page_entry.page_name,
            state="succeeded",
            text_preview=text[:60],
        )
    except Exception as exc:  # per-page re-run failure is recorded on the page, not raised
        logger.exception(
            "Per-page re-run OCR failed; recording failure on page",
            extra={"context": f"project_id={spec.project_id!r}, page_idx={page_idx}"},
        )
        done_page = PageResult(
            page_idx=page_idx,
            page_name=page_entry.page_name,
            state="failed",
            error=str(exc),
        )

    update_page_result(spec, done_page)
    return done_page
