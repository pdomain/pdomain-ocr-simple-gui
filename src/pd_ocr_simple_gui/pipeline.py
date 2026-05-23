"""OCR pipeline orchestration for pd-ocr-simple-gui.

Entry points:

* :func:`collect_images` — resolve a file or directory to a sorted list of
  image paths.
* :func:`run_project` — async driver that iterates pages, dispatches OCR via
  ``LocalStageDispatcher``, writes sidecars and ``.txt`` files, and fires a
  status callback after each page.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from pd_ocr_simple_gui.models import ProjectSpec, ProjectStatus

# Image extensions we recognise (case-insensitive).
_IMAGE_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".tiff", ".tif"})

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class StageResultLike(Protocol):
    """Subset of stage result required by pipeline/page extraction."""

    metadata: Mapping[str, object]


class OCRDispatcher(Protocol):
    """Structural type for OCR dispatchers used by this module."""

    async def run_stage(
        self,
        stage_id: str,
        page_id: str,
        **kwargs: object,
    ) -> StageResultLike:
        """Run an OCR stage and return a result with metadata."""
        ...


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
    if child_type == "WORD":
        # Line-level block containing words: join with spaces
        return " ".join(parts)
    # Block containing child blocks: single newline between them
    return "\n".join(parts)


async def run_project(
    spec: ProjectSpec,
    dispatcher: OCRDispatcher,
    status_callback: Callable[[ProjectStatus], Awaitable[None]],
) -> None:
    """Orchestrate OCR for all pages in *spec.source_path*.

    For each image:

    1. Calls ``dispatcher.run_stage("ocr", page_id, image_path=..., engine=...,
       language=...)`` to get a :class:`~pd_ocr_ops.gpu.types.StageResult`.
    2. Extracts the first page dict from ``result.metadata["pages"]``.
    3. Writes the page sidecar JSON and plain-text file via storage helpers.
    4. Updates the per-page :class:`~pd_ocr_simple_gui.models.PageResult` and
       calls *status_callback* with the updated
       :class:`~pd_ocr_simple_gui.models.ProjectStatus`.

    The project must already be written to storage with a ``pages`` list
    matching the discovered images (page names = image filenames) before
    ``run_project`` is called.  Callers are responsible for seeding the
    initial project state.
    """
    from pd_ocr_simple_gui.models import PageResult, ProjectStatus
    from pd_ocr_simple_gui.storage import (
        read_project,
        update_page_result,
        write_combined_txt,
        write_page_sidecar,
        write_project,
        write_txt,
    )

    images = await collect_images(spec.source_path)
    total = len(images)

    # Mark project as running
    _, current_status = read_project(spec.project_id)
    running_status = ProjectStatus(
        project_id=spec.project_id,
        state="running",
        page_count=total,
        pages_done=0,
        pages=current_status.pages,
    )
    write_project(spec, running_status)

    for idx, img_path in enumerate(images):
        page_id = f"{spec.project_id}/{idx}"

        # Mark page as running
        page_running = PageResult(
            page_idx=idx,
            page_name=img_path.name,
            state="running",
        )
        update_page_result(spec, page_running)

        try:
            stage_result = await dispatcher.run_stage(
                "ocr",
                page_id,
                image_path=str(img_path),
                engine=spec.engine,
                language=spec.language,
            )
            # metadata["pages"] is a list; take the first page dict
            page_dict = first_page_dict(stage_result.metadata)
            text = extract_text(page_dict)

            write_page_sidecar(spec, idx, page_dict)
            write_txt(spec, idx, text)

            page_done = PageResult(
                page_idx=idx,
                page_name=img_path.name,
                state="succeeded",
                text_preview=text[:60],
            )
        except Exception as exc:  # noqa: BLE001  # per-page OCR failure must not abort the whole batch
            page_done = PageResult(
                page_idx=idx,
                page_name=img_path.name,
                state="failed",
                error=str(exc),
            )

        update_page_result(spec, page_done)
        _, updated_status = read_project(spec.project_id)
        await status_callback(updated_status)

    # Final state
    _, final_status = read_project(spec.project_id)
    all_done = all(p.state == "succeeded" for p in final_status.pages)
    final_state = "succeeded" if all_done else "failed"
    terminal_status = ProjectStatus(
        project_id=spec.project_id,
        state=final_state,
        page_count=total,
        pages_done=sum(1 for p in final_status.pages if p.state == "succeeded"),
        pages=final_status.pages,
    )
    write_project(spec, terminal_status)

    if spec.combined_txt:
        write_combined_txt(spec, terminal_status)
