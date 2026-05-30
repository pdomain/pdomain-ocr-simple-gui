"""Project storage helpers — sidecar IO, project dir management."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import TypeAlias, cast

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus

logger = logging.getLogger(__name__)

_PROJECTS_ROOT_DEFAULT: Path = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"


def _projects_root() -> Path:
    """Return the projects root directory.

    Reads ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT`` from the environment so that the
    test suite (and CI) can redirect storage without touching the real home
    directory.  Falls back to the shipped default when the var is not set.
    """
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT")
    return Path(raw) if raw else _PROJECTS_ROOT_DEFAULT


JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


def _read_json_object(path: Path) -> JSONObject:
    """Read a JSON file and ensure it contains an object with string keys."""
    data = cast("object", json.loads(path.read_text()))
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return cast("JSONObject", data)


# Allowlist: only alphanumeric, hyphens, and underscores.
# UUIDs (the canonical project_id form) use hex digits and hyphens; this is intentionally
# narrow — forward slashes, dots, backslashes, null bytes, and percent signs are all banned.
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_project_id(project_id: str) -> None:
    """Raise ValueError if project_id contains traversal-unsafe characters.

    Two defences in depth:
    1. Allowlist check — only [A-Za-z0-9_-] permitted; bans dots, slashes,
       backslashes, null bytes, percent signs, etc.
    2. Path containment — the resolved path must be a direct child of
       _projects_root() (not _projects_root() itself, not above it).

    Call this at the API boundary, before any filesystem operation.
    """
    if not _PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError(
            f"Invalid project_id {project_id!r}: only A-Za-z0-9, hyphens and underscores allowed"
        )
    # Containment check against the resolved root (handles symlinks on the root)
    _root = _projects_root()
    resolved_root = _root.resolve()
    candidate = (_root / project_id).resolve()
    # Must be strictly under the root, not equal to it
    if candidate == resolved_root or not str(candidate).startswith(str(resolved_root) + "/"):
        raise ValueError(f"project_id {project_id!r} resolves outside the project store")


def get_project_dir(project_id: str) -> Path:
    """Return the project directory for the given project_id."""
    return _projects_root() / project_id


def write_project(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Write project.json to the project directory."""
    proj_dir = get_project_dir(spec.project_id)
    proj_dir.mkdir(parents=True, exist_ok=True)
    data: JSONObject = {
        "spec": json.loads(spec.model_dump_json()),
        "status": json.loads(status.model_dump_json()),
    }
    _ = (proj_dir / "project.json").write_text(json.dumps(data, indent=2))


def read_project(project_id: str) -> tuple[ProjectSpec, ProjectStatus]:
    """Read spec and status from project.json; raises FileNotFoundError if missing."""
    proj_file = get_project_dir(project_id) / "project.json"
    if not proj_file.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    data = _read_json_object(proj_file)
    spec = ProjectSpec.model_validate(data["spec"])
    status = ProjectStatus.model_validate(data["status"])
    return spec, status


def _page_name_for_idx(spec: ProjectSpec, status: ProjectStatus, idx: int) -> str:
    """Return the page_name for a given index from the status pages list."""
    for page in status.pages:
        if page.page_idx == idx:
            return page.page_name
    raise FileNotFoundError(f"Page index {idx} not found in project {spec.project_id}")


def _pages_dir(spec: ProjectSpec) -> Path:
    return get_project_dir(spec.project_id) / "pages"


def write_page_sidecar(spec: ProjectSpec, idx: int, page_dict: JSONObject) -> None:
    """Write a per-page JSON sidecar. Reads status to resolve page_name."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    pages_dir = _pages_dir(spec)
    pages_dir.mkdir(parents=True, exist_ok=True)
    _ = (pages_dir / f"{page_name}.json").write_text(json.dumps(page_dict, indent=2))


def read_page_sidecar(spec: ProjectSpec, idx: int) -> JSONObject:
    """Read a per-page JSON sidecar; raises FileNotFoundError if missing."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    sidecar_path = _pages_dir(spec) / f"{page_name}.json"
    if not sidecar_path.exists():
        raise FileNotFoundError(f"Sidecar not found for page {idx} in {spec.project_id}")
    return _read_json_object(sidecar_path)


def write_txt(spec: ProjectSpec, idx: int, text: str) -> None:
    """Write plain-text OCR output for one page."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    pages_dir = _pages_dir(spec)
    pages_dir.mkdir(parents=True, exist_ok=True)
    _ = (pages_dir / f"{page_name}.txt").write_text(text)


def write_combined_txt(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Concatenate all per-page .txt files into combined.txt."""
    pages_dir = _pages_dir(spec)
    parts: list[str] = []
    for page in sorted(status.pages, key=lambda p: p.page_idx):
        txt_path = pages_dir / f"{page.page_name}.txt"
        if txt_path.exists():
            parts.append(txt_path.read_text())
    combined = "\n\n".join(parts)
    _ = (get_project_dir(spec.project_id) / "combined.txt").write_text(combined)


# Match anything that looks like a filesystem-unsafe character; collapsed to "_".
_UNSAFE_FS_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename_stem(name: str, fallback: str) -> str:
    """Return a filesystem-safe stem derived from *name*, or *fallback*.

    Used to name the combined-text output file in ``spec.output_dir``.
    """
    cleaned = _UNSAFE_FS_CHARS.sub("_", name).strip("._-")
    return cleaned or fallback


def _output_dir(spec: ProjectSpec) -> Path | None:
    """Return spec.output_dir as a Path, or None when not configured."""
    if not spec.output_dir:
        return None
    return Path(spec.output_dir)


def write_output_page_files(
    spec: ProjectSpec,
    idx: int,
    page_name: str,
    text: str,
    sidecar_payload: JSONObject | None,
) -> None:
    """Mirror per-page outputs into ``spec.output_dir``.

    Always writes ``<output_dir>/<page_stem>.txt``.  When *sidecar_payload*
    is non-None, additionally writes ``<output_dir>/<page_stem>.json``.  The
    pipeline now always passes the sidecar payload (no save_json knob), so the
    ``.json`` mirror is always written when an output dir is configured; the
    ``None`` branch is retained only for callers that have no sidecar.  No-op
    when ``spec.output_dir`` is empty.
    """
    _ = idx  # kept for future per-index disambiguation; signature stays stable
    out = _output_dir(spec)
    if out is None:
        return
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(page_name).stem or page_name
    (out / f"{stem}.txt").write_text(text, encoding="utf-8")
    if sidecar_payload is not None:
        (out / f"{stem}.json").write_text(json.dumps(sidecar_payload, indent=2), encoding="utf-8")


def write_output_combined_txt(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Write the combined per-project ``.txt`` into ``spec.output_dir``.

    Filename is derived from ``spec.name`` (filesystem-sanitised); falls back
    to ``combined.txt`` when the spec name is empty or sanitises to empty.
    No-op when ``spec.output_dir`` is empty.
    """
    out = _output_dir(spec)
    if out is None:
        return
    out.mkdir(parents=True, exist_ok=True)
    pages_dir = _pages_dir(spec)
    parts: list[str] = []
    for page in sorted(status.pages, key=lambda p: p.page_idx):
        txt_path = pages_dir / f"{page.page_name}.txt"
        if txt_path.exists():
            parts.append(txt_path.read_text())
    combined = "\n\n".join(parts)
    stem = _safe_filename_stem(spec.name, "combined")
    (out / f"{stem}.txt").write_text(combined, encoding="utf-8")


def list_projects() -> list[tuple[ProjectSpec, ProjectStatus]]:
    """Return all known projects from the projects root."""
    root = _projects_root()
    if not root.exists():
        return []
    results: list[tuple[ProjectSpec, ProjectStatus]] = []
    for proj_dir in sorted(root.iterdir()):
        proj_file = proj_dir / "project.json"
        if proj_file.exists():
            try:
                spec, status = read_project(proj_dir.name)
                results.append((spec, status))
            except Exception:  # skip unreadable project dirs; listing must not fail
                logger.exception(
                    "Skipping unreadable project directory during listing",
                    extra={"context": f"read_project({proj_dir.name!r})"},
                )
    return results


def delete_project(project_id: str) -> None:
    """Delete a project directory. No-op if it doesn't exist."""
    proj_dir = get_project_dir(project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir)


def update_page_result(spec: ProjectSpec, page_result: PageResult) -> None:
    """Update a single PageResult in the stored project status."""
    s, status = read_project(spec.project_id)
    new_pages = [p if p.page_idx != page_result.page_idx else page_result for p in status.pages]
    pages_done = sum(1 for p in new_pages if p.state == "succeeded")
    all_states = {p.state for p in new_pages}
    if "running" in all_states:
        agg_state: str = "running"
    elif "failed" in all_states:
        agg_state = "failed"
    elif all_states == {"succeeded"}:
        agg_state = "succeeded"
    elif "queued" in all_states:
        agg_state = "queued"
    else:
        agg_state = status.state
    new_status = ProjectStatus(
        project_id=status.project_id,
        state=agg_state,  # type: ignore[arg-type]  # str literal accepted by ProjectStatusState; not narrowed
        page_count=status.page_count,
        pages_done=pages_done,
        pages=new_pages,
        # Preserve the free-text progress message — pipeline.py stamps it
        # outside the per-page state machine, so per-page updates must not
        # silently drop it.
        progress_message=status.progress_message,
    )
    write_project(s, new_status)
