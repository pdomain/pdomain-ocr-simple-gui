"""OCR pipeline orchestration for pdomain-ocr-simple-gui.

Entry points:

* :func:`collect_images` — resolve a file or directory to a sorted list of
  image paths.
* :func:`run_project` — async driver that chunks pages into batches, dispatches
  OCR via ``LocalStageDispatcher.run_ocr_batch``, writes sidecars and ``.txt``
  files, and fires a status callback after each chunk.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast

from pdomain_ops.gpu.types import OcrBatchRequest  # pyright: ignore[reportMissingTypeStubs]

from pdomain_ocr_simple_gui.statecharts.job_lifecycle import assert_job_transition

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from pdomain_ocr_simple_gui.models import ProjectSpec, ProjectStatus


# Image extensions we recognise (case-insensitive).
_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        # JPEG 2000 family — Pillow handles via OpenJPEG.
        ".jp2",
        ".j2k",
        ".jpf",
        ".jpx",
        ".jpm",
    }
)

# Default batch size when spec.batch_pages is None.
_DEFAULT_BATCH_PAGES: int = 8

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
ApiJobState: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class OCRDispatcher(Protocol):
    """Structural type for OCR dispatchers used by this module.

    NOTE: ``run_ocr_batch`` does not accept a device parameter — device
    selection is handled internally by the LocalStageDispatcher (VRAM sizing
    + OOM backoff + CPU fallback).  The user's device choice (spec.device)
    is therefore not forwarded to the batch seam.  This is a known gap:
    when the pdomain-ops OcrBatchRequest gains a device field, wire
    spec.device through here.  See: follow-up on device override in
    Wave-3 batch seam (ocr-container-meta).
    """

    async def run_ocr_batch(
        self,
        req: object,
    ) -> list[dict[str, object]]:
        """Run batched OCR on multiple pages.

        Accepts image bytes; returns one page dict per input image, in order.
        """
        ...


def resolve_device(choice: str) -> str | None:
    """Translate a job's device choice into a run_stage override.

    - "auto" -> None (dispatcher auto-detects via pick_device)
    - "cpu"  -> "cpu"
    - "gpu"  -> the detected accelerator ("local"/"mps"); falls back to the
      detected device, which run_stage degrades to cpu when no GPU impl.

    NOTE: This function is preserved for informational use but is NOT
    forwarded to run_ocr_batch (which has no device parameter yet).
    """
    if choice == "cpu":
        return "cpu"
    if choice == "gpu":
        try:
            from pdomain_ops.gpu.device import pick_device  # pyright: ignore[reportMissingTypeStubs]

            return pick_device()
        except (ImportError, ValueError, RuntimeError):
            return None
    return None


def _json_object_or_none(value: object) -> JsonObject | None:
    """Return value as a JSON object when shape looks like dict[str, ...]."""
    if not isinstance(value, dict):
        return None
    raw_dict = cast("dict[object, object]", value)
    if not all(isinstance(key, str) for key in raw_dict):
        return None
    return cast("JsonObject", raw_dict)


def _json_object_list(value: object) -> list[JsonObject]:
    """Filter a JSON-like list down to dict members only."""
    if not isinstance(value, list):
        return []
    raw_list = cast("list[object]", value)
    objects: list[JsonObject] = []
    for item in raw_list:
        obj = _json_object_or_none(item)
        if obj is not None:
            objects.append(obj)
    return objects


def first_page_dict(metadata: Mapping[str, object]) -> JsonObject:
    """Extract the first page object from stage metadata."""
    pages_list = _json_object_list(metadata.get("pages"))
    return pages_list[0] if pages_list else {}


def _bbox_xywh_from_bounding_box(bb: object) -> JsonObject | None:
    """Convert a pdomain-book-tools bounding_box dict to {x, y, w, h} normalized.

    Source shape::

        {
            "top_left":     {"x": float, "y": float, "is_normalized": bool},
            "bottom_right": {"x": float, "y": float, "is_normalized": bool},
            "is_normalized": bool,
        }

    Returns ``None`` when the shape isn't recognisable.  ``is_normalized``
    is treated as true by default — these come from DocTR which always
    emits normalized geometry; we currently have no pixel-space fallback.
    """
    obj = _json_object_or_none(bb)
    if obj is None:
        return None
    tl = _json_object_or_none(obj.get("top_left"))
    br = _json_object_or_none(obj.get("bottom_right"))
    if tl is None or br is None:
        return None
    tl_x = tl.get("x")
    tl_y = tl.get("y")
    br_x = br.get("x")
    br_y = br.get("y")
    if not (
        isinstance(tl_x, (int, float))
        and isinstance(tl_y, (int, float))
        and isinstance(br_x, (int, float))
        and isinstance(br_y, (int, float))
    ):
        return None
    return {
        "x": float(tl_x),
        "y": float(tl_y),
        "w": float(br_x) - float(tl_x),
        "h": float(br_y) - float(tl_y),
    }


def extract_words(page_dict: JsonObject) -> list[JsonObject]:
    """Flatten a pdomain-book-tools ``Page.to_dict()`` tree to word records.

    Walks the recursive ``Page → Block → … → Word`` tree (where ``Word``
    nodes carry ``type == "Word"``, a ``text`` string, a ``bounding_box``
    dict and an ``ocr_confidence`` float) and returns a flat list of::

        {"text": str, "bbox": {"x": float, "y": float, "w": float, "h": float},
         "confidence": float}

    Coordinates are page-relative (0..1, top-left origin), matching what
    ``WordBboxOverlay`` and ``/api/pages/{id}/{idx}/words`` already expect.
    Words missing geometry are skipped — they can't be rendered as overlays.
    """
    results: list[JsonObject] = []

    def _walk(node: JsonObject) -> None:
        node_type = node.get("type")
        if node_type == "Word":
            text_value = node.get("text")
            if not isinstance(text_value, str) or not text_value:
                return
            bbox = _bbox_xywh_from_bounding_box(node.get("bounding_box"))
            if bbox is None:
                return
            conf_value = node.get("ocr_confidence")
            confidence = float(conf_value) if isinstance(conf_value, (int, float)) else 0.0
            results.append({"text": text_value, "bbox": bbox, "confidence": confidence})
            return
        items_value = node.get("items")
        if not isinstance(items_value, list):
            return
        for item in items_value:
            child = _json_object_or_none(item)
            if child is not None:
                _walk(child)

    _walk(page_dict)
    return results


def _page_dimensions(page_dict: JsonObject) -> tuple[int, int]:
    """Return (width, height) from a page dict, defaulting to (0, 0)."""
    width_raw = page_dict.get("width")
    height_raw = page_dict.get("height")
    width = int(width_raw) if isinstance(width_raw, (int, float)) else 0
    height = int(height_raw) if isinstance(height_raw, (int, float)) else 0
    return width, height


def build_sidecar_payload(page_dict: JsonObject, text: str) -> JsonObject:
    """Wrap a raw ``Page.to_dict()`` with normalized top-level keys.

    Adds ``text``, ``width``, ``height``, and a flat ``words`` array so that
    consumers (``GET /api/pages/{id}/{idx}`` and ``/words``) don't need to
    re-walk the recursive tree.  The original tree is preserved under the
    same keys it shipped with — ``items``, ``bounding_box``, etc. — so a
    full sidecar is still self-describing.
    """
    width, height = _page_dimensions(page_dict)
    payload: JsonObject = dict(page_dict)
    payload["text"] = text
    if width:
        payload["width"] = width
    if height:
        payload["height"] = height
    payload["words"] = cast("JsonValue", extract_words(page_dict))
    return payload


async def collect_images(source_path: str) -> list[Path]:
    """Return a sorted list of image paths from *source_path*.

    If *source_path* is a file and has an image extension, returns
    ``[Path(source_path)]``.  If it is a directory, returns all immediate
    children whose suffix (case-insensitive) is in ``_IMAGE_SUFFIXES``,
    sorted by name.  Returns ``[]`` for missing paths.
    """
    p = Path(source_path)
    if not p.exists():
        return []
    if p.is_file():
        if p.suffix.lower() in _IMAGE_SUFFIXES:
            return [p]
        return []
    # Directory
    return sorted(child for child in p.iterdir() if child.suffix.lower() in _IMAGE_SUFFIXES)


def extract_text(page_dict: JsonObject) -> str:
    """Extract plain text from a ``Page.to_dict()`` dict.

    The dict is a recursive structure mirroring the ``Block``/``Word`` tree:

    * ``{"type": "Page", "items": [...]}``
    * ``{"type": "Block", "items": [...]}``
    * ``{"type": "Word", "text": "..."}``

    Blocks are separated by double newlines; words within a line (block
    ``child_type == "WORD"``) are joined with spaces; nested blocks are
    separated by single newlines.  This mirrors :meth:`Page.text` semantics.
    """
    node_type_value = page_dict.get("type")
    if node_type_value == "Word":
        text_value = page_dict.get("text")
        return text_value if isinstance(text_value, str) else ""

    items_value = page_dict.get("items")
    if not isinstance(items_value, list):
        return ""

    child_type_value = page_dict.get("child_type")
    child_type = child_type_value if isinstance(child_type_value, str) else None
    node_type = node_type_value if isinstance(node_type_value, str) else ""

    parts: list[str] = []
    for item in items_value:
        child = _json_object_or_none(item)
        if child is None:
            continue
        text = extract_text(child)
        if text:
            parts.append(text)
    if not parts:
        return ""
    if node_type == "Page":
        # Top-level page: double newline between blocks
        return "\n\n".join(parts)
    if child_type in ("WORD", "WORDS"):
        # Line-level block containing words: join with spaces.
        # "WORDS" is the canonical BlockChildType value; "WORD" was the
        # legacy DocTR shape accepted for back-compat.
        return " ".join(parts)
    # Block containing child blocks: single newline between them
    return "\n".join(parts)


async def run_project(
    spec: ProjectSpec,
    dispatcher: OCRDispatcher,
    status_callback: Callable[[ProjectStatus], Awaitable[None]],
) -> None:
    """Orchestrate OCR for all pages in *spec.source_path*.

    Pages are grouped into chunks of ``spec.batch_pages`` (default
    :data:`_DEFAULT_BATCH_PAGES`).  For each chunk:

    1. Reads image bytes for each page in the chunk.
    2. Builds an :class:`~pdomain_ops.gpu.types.OcrBatchRequest` and calls
       ``dispatcher.run_ocr_batch(req)``.
    3. For each returned page dict, runs ``reorganize_page`` + text
       normalizations + sidecar/txt writes.
    4. On exception (non-OOM or any), marks only that chunk's pages as
       ``failed`` and continues to the next chunk — one bad chunk does
       not abort the whole job.
    5. Calls *status_callback* after each chunk.

    **Device note:** ``run_ocr_batch`` does not accept a device parameter;
    device selection (VRAM sizing, OOM backoff, CPU fallback) is handled
    internally by the LocalStageDispatcher.  The user's ``spec.device``
    choice is therefore not forwarded.  When the pdomain-ops
    ``OcrBatchRequest`` gains a device field this should be wired here.
    See: follow-up on device override in Wave-3 batch seam.

    The project must already be written to storage with a ``pages`` list
    matching the discovered images (page names = image filenames) before
    ``run_project`` is called.  Callers are responsible for seeding the
    initial project state.
    """
    from pdomain_ocr_simple_gui.models import PageResult, ProjectStatus
    from pdomain_ocr_simple_gui.storage import (
        read_project,
        write_combined_txt,
        write_output_combined_txt,
        write_output_page_files,
        write_page_sidecar,
        write_project,
        write_txt,
    )

    images = await collect_images(spec.source_path)
    total = len(images)

    # Resolve batch size: honor spec.batch_pages when set; fall back to default.
    batch_size: int = (
        spec.batch_pages if spec.batch_pages is not None and spec.batch_pages >= 1 else _DEFAULT_BATCH_PAGES
    )

    def _persist_message(message: str | None) -> ProjectStatus:
        """Set ``progress_message`` on the stored status and persist it."""
        _, prev = read_project(spec.project_id)
        next_status = prev.model_copy(update={"progress_message": message})
        write_project(spec, next_status)
        return next_status

    # Mark project as running
    _, current_status = read_project(spec.project_id)
    running_state = cast("ApiJobState", assert_job_transition(current_status.state, "start"))
    running_status = ProjectStatus(
        project_id=spec.project_id,
        state=running_state,
        page_count=total,
        pages_done=0,
        pages=current_status.pages,
    )
    write_project(spec, running_status)

    def _update_page_result_while_running(page_result: PageResult) -> None:
        """Update a page without letting page aggregation terminalize the project."""
        stored_spec, current = read_project(spec.project_id)
        next_pages = [
            page if page.page_idx != page_result.page_idx else page_result for page in current.pages
        ]
        next_status = current.model_copy(
            update={
                "state": running_state,
                "pages_done": sum(1 for page in next_pages if page.state == "succeeded"),
                "pages": next_pages,
            },
        )
        write_project(stored_spec, next_status)

    # Warm-up message before any batch starts — DocTR's first run may pull
    # ~200 MB of weights from Hugging Face plus a GPU model load.
    warm_status = _persist_message(
        "Loading OCR engine — first run may download ~200 MB to ~/.cache/huggingface",
    )
    await status_callback(warm_status)

    completed = 0

    # Process pages in chunks
    chunk_start = 0
    while chunk_start < total:
        chunk_end = min(chunk_start + batch_size, total)
        chunk_indices = list(range(chunk_start, chunk_end))
        chunk_images = [images[i] for i in chunk_indices]

        # Mark chunk pages as running
        for idx, img_path in zip(chunk_indices, chunk_images, strict=True):
            _update_page_result_while_running(
                PageResult(page_idx=idx, page_name=img_path.name, state="running"),
            )

        try:
            # Build OcrBatchRequest — bytes-based, not path-based.
            # OcrBatchRequest is imported from pdomain_ops.gpu.types (>= 0.4.0).
            image_bytes = [img_path.read_bytes() for img_path in chunk_images]
            source_ids = [f"{spec.project_id}/{idx}" for idx in chunk_indices]
            req = OcrBatchRequest(
                images=image_bytes,
                source_identifiers=source_ids,
                engine=spec.engine,
                language=spec.language,
                device=resolve_device(spec.device),
            )

            page_dicts: list[dict[str, object]] = await dispatcher.run_ocr_batch(req)

            # Post-process each page in the successful chunk
            for local_i, (idx, img_path) in enumerate(zip(chunk_indices, chunk_images, strict=True)):
                raw_page_dict = cast("JsonObject", page_dicts[local_i])

                # Round-trip through pdomain-book-tools Page so reorganize_page()
                # clusters flat OCR words into lines/paragraphs/blocks.
                from pdomain_book_tools.ocr.page import Page

                raw_text = extract_text(raw_page_dict)
                reorganized_dict: JsonObject = raw_page_dict
                reorganized_text = ""
                try:
                    page_obj = Page.from_dict(raw_page_dict)
                    page_obj.reorganize_page(
                        emit_illustration_placeholders=spec.emit_illustration_placeholders,
                    )
                    reorganized_dict = cast("JsonObject", page_obj.to_dict())
                    reorganized_text = page_obj.text
                except Exception:
                    logger.exception(
                        "reorganize_page() failed; falling back to raw OCR dict",
                        extra={"context": f"page_idx={idx}, image={img_path.name!r}"},
                    )

                # Reorganize needs bbox geometry; fall back to extract_text when empty
                if reorganized_text.strip():
                    page_dict = reorganized_dict
                    text = reorganized_text
                else:
                    page_dict = raw_page_dict
                    text = raw_text

                # Apply post-OCR text normalizations (curly quotes, em-dashes)
                try:
                    from pdomain_book_tools.ocr import apply_text_normalizations

                    text = apply_text_normalizations(
                        text,
                        straight_quotes=spec.straight_quotes,
                        em_dash_to_double_hyphen=spec.em_dash_to_double_hyphen,
                    )
                except ImportError:
                    logger.debug(
                        "apply_text_normalizations unavailable; skipping cleanup",
                    )

                sidecar_payload = build_sidecar_payload(page_dict, text)
                write_page_sidecar(spec, idx, sidecar_payload)
                write_txt(spec, idx, text)

                # Mirror per-page artifacts into spec.output_dir for download.
                # The sidecar .json is ALWAYS mirrored (no save_json knob) —
                # the bbox overlay needs it (B-HOME-011 cleanup).
                write_output_page_files(
                    spec,
                    idx,
                    img_path.name,
                    text,
                    sidecar_payload,
                )

                _update_page_result_while_running(
                    PageResult(
                        page_idx=idx,
                        page_name=img_path.name,
                        state="succeeded",
                        text_preview=text[:60],
                    ),
                )
                completed += 1

        except Exception as exc:  # chunk failure must not abort the job
            logger.exception(
                "OCR batch failed for chunk; recording failure and continuing",
                extra={"context": (f"chunk_start={chunk_start}, chunk_end={chunk_end}")},
            )
            # Mark all pages in the failed chunk as failed
            for idx, img_path in zip(chunk_indices, chunk_images, strict=True):
                _update_page_result_while_running(
                    PageResult(
                        page_idx=idx,
                        page_name=img_path.name,
                        state="failed",
                        error=str(exc),
                    ),
                )
            completed += len(chunk_indices)

        # Fire progress callback after each chunk
        _ = _persist_message(f"Processed {completed}/{total} pages")
        _, updated_status = read_project(spec.project_id)
        await status_callback(updated_status)

        chunk_start = chunk_end

    # Surface a "Writing outputs" message while we finalize the combined-txt
    # mirror. combined.txt is always written now (B-HOME-011 cleanup).
    writing_status = _persist_message("Writing outputs")
    await status_callback(writing_status)

    # Final state — clear progress_message so stale text doesn't linger in
    # the polled GET /api/jobs/{id} response.
    _, final_status = read_project(spec.project_id)
    all_done = all(p.state == "succeeded" for p in final_status.pages)
    terminal_event = "succeed" if all_done else "fail"
    final_state = cast("ApiJobState", assert_job_transition(final_status.state, terminal_event))
    terminal_status = ProjectStatus(
        project_id=spec.project_id,
        state=final_state,
        page_count=total,
        pages_done=sum(1 for p in final_status.pages if p.state == "succeeded"),
        pages=final_status.pages,
        progress_message=None,
    )
    write_project(spec, terminal_status)

    # combined.txt is ALWAYS written (canonical + output mirror) — the
    # combined download + previews depend on it (B-HOME-011 cleanup).
    write_combined_txt(spec, terminal_status)
    write_output_combined_txt(spec, terminal_status)
