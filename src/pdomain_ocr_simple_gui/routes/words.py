"""Words route -- GET /api/pages/{job_id}/{idx}/words.

Returns a flat list of word overlays extracted from the per-page sidecar
that ``run_project`` writes after each OCR stage.  The sidecar stores a
DocTR ``Page.export()`` dict (nested blocks -> lines -> words); this module
flattens it to ``[{text, bbox: {x,y,w,h}, confidence}]`` in page-relative
coordinates (0.0-1.0 range, origin top-left).

Deviation from plan sketch: the plan referenced
``pdomain_ocr_simple_gui.pages.read_page_result``, which does not exist in this
repo.  The equivalent data lives in the per-page JSON sidecar written by
``storage.write_page_sidecar``.  ``load_page_words`` reads that sidecar
directly via ``storage.read_page_sidecar`` + ``storage.read_project``, then
walks the DocTR tree to extract words.  The monkeypatch target
``pdomain_ocr_simple_gui.routes.words.load_page_words`` is preserved exactly as
the plan specifies.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pdomain_ocr_simple_gui.pipeline import JsonObject

_Numeric = float | int

router = APIRouter()


class Bbox(BaseModel):
    """Bounding box in page-relative coordinates (0.0-1.0)."""

    x: float
    y: float
    w: float
    h: float


class Word(BaseModel):
    """A single OCR word with position and confidence."""

    text: str
    bbox: Bbox
    confidence: float


class WordsResponse(BaseModel):
    """Response body for GET /api/pages/{job_id}/{idx}/words."""

    words: list[Word]


def _read_prebaked_words(page_dict: JsonObject) -> list[dict[str, object]] | None:
    """Return the flat ``words`` array baked into the sidecar by the pipeline.

    The pipeline (``build_sidecar_payload``) now writes a normalized
    ``words: [{text, bbox: {x, y, w, h}, confidence}]`` list at the top of
    each sidecar.  When present and well-formed, prefer it over walking
    the recursive tree.  Returns ``None`` when the key is absent or the
    shape doesn't validate (older sidecars), so the caller can fall back.
    """
    raw = page_dict.get("words")
    if not isinstance(raw, list):
        return None
    out: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        text = item.get("text")
        bbox = item.get("bbox")
        conf = item.get("confidence")
        if not isinstance(text, str) or not isinstance(bbox, dict):
            return None
        bx = bbox.get("x")
        by = bbox.get("y")
        bw = bbox.get("w")
        bh = bbox.get("h")
        if not (
            isinstance(bx, (int, float))
            and isinstance(by, (int, float))
            and isinstance(bw, (int, float))
            and isinstance(bh, (int, float))
        ):
            return None
        confidence = float(conf) if isinstance(conf, (int, float)) else 0.0
        out.append(
            {
                "text": text,
                "bbox": {
                    "x": float(bx),
                    "y": float(by),
                    "w": float(bw),
                    "h": float(bh),
                },
                "confidence": confidence,
            }
        )
    return out


def _extract_words_from_page_dict(page_dict: JsonObject) -> list[dict[str, object]]:
    """Walk a DocTR Page.export() dict and return a flat list of word dicts.

    The DocTR export structure is:
        Page → blocks[] → lines[] → words[]

    Each word has:
        ``value`` (str), ``confidence`` (float),
        ``geometry`` ([[xmin, ymin], [xmax, ymax]]) in relative coords.

    Returns dicts with keys ``text``, ``bbox`` ({x, y, w, h}), ``confidence``.
    """
    results: list[dict[str, object]] = []
    blocks_raw = page_dict.get("blocks")
    if not isinstance(blocks_raw, list):
        return results
    for block in blocks_raw:
        if not isinstance(block, dict):
            continue
        lines_raw = block.get("lines")
        if not isinstance(lines_raw, list):
            continue
        for line in lines_raw:
            if not isinstance(line, dict):
                continue
            words_raw = line.get("words")
            if not isinstance(words_raw, list):
                continue
            for word in words_raw:
                if not isinstance(word, dict):
                    continue
                value = word.get("value")
                confidence = word.get("confidence")
                geometry = word.get("geometry")
                if not isinstance(value, str):
                    continue
                if not isinstance(confidence, float | int):
                    continue
                if (  # geometry is [[xmin, ymin], [xmax, ymax]]
                    not isinstance(geometry, list)
                    or len(geometry) != 2
                    or not isinstance(geometry[0], list)
                    or not isinstance(geometry[1], list)
                    or len(geometry[0]) != 2
                    or len(geometry[1]) != 2
                ):
                    continue
                g0, g1 = geometry[0], geometry[1]
                if not (
                    isinstance(g0[0], _Numeric)
                    and isinstance(g0[1], _Numeric)
                    and isinstance(g1[0], _Numeric)
                    and isinstance(g1[1], _Numeric)
                ):
                    continue
                xmin: float = float(g0[0])
                ymin: float = float(g0[1])
                xmax: float = float(g1[0])
                ymax: float = float(g1[1])
                results.append(
                    {
                        "text": value,
                        "bbox": {
                            "x": xmin,
                            "y": ymin,
                            "w": xmax - xmin,
                            "h": ymax - ymin,
                        },
                        "confidence": float(confidence),
                    }
                )
    return results


def load_page_words(job_id: str, idx: int) -> Iterable[dict[str, object]] | None:
    """Read the page sidecar and return a flat iterable of word dicts.

    Returns ``None`` when the project or page sidecar does not exist,
    which the route maps to a 404 response.

    This function is defined at module top-level so tests can monkeypatch
    ``pdomain_ocr_simple_gui.routes.words.load_page_words`` without ceremony.
    """
    from pdomain_ocr_simple_gui.storage import (
        read_page_sidecar,
        read_project,
        validate_project_id,
    )

    with contextlib.suppress(ValueError):
        validate_project_id(job_id)
    # If the project or sidecar is missing, return None → 404
    try:
        spec, _ = read_project(job_id)
    except FileNotFoundError:
        return None
    try:
        sidecar = read_page_sidecar(spec, idx)
    except FileNotFoundError:
        return None
    # Prefer the normalized flat ``words`` baked into the sidecar by the
    # pipeline; fall back to the DocTR-shaped walker for older sidecars
    # written before the build_sidecar_payload helper landed.
    prebaked = _read_prebaked_words(sidecar)
    if prebaked is not None:
        return prebaked
    return _extract_words_from_page_dict(sidecar)


@router.get(
    "/api/pages/{job_id}/{idx}/words",
    response_model=WordsResponse,
)
def get_words(job_id: str, idx: int) -> WordsResponse:
    """Return word overlays for the given page.

    Each word includes its text, a page-relative bounding box
    ``{x, y, w, h}`` (values in 0.0-1.0 range), and the OCR confidence
    score.  Returns 404 if the job or page sidecar does not exist.
    """
    payload = load_page_words(job_id, idx)
    if payload is None:
        raise HTTPException(status_code=404, detail="page not found")
    return WordsResponse(words=[Word.model_validate(w) for w in payload])
