"""Project storage helpers — sidecar IO, project dir management."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pd_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus

_PROJECTS_ROOT: Path = Path.home() / ".local" / "share" / "pd-suite" / "simple-gui" / "projects"


def get_project_dir(project_id: str) -> Path:
    """Return the project directory for the given project_id."""
    return _PROJECTS_ROOT / project_id


def write_project(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Write project.json to the project directory."""
    proj_dir = get_project_dir(spec.project_id)
    proj_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "spec": json.loads(spec.model_dump_json()),
        "status": json.loads(status.model_dump_json()),
    }
    (proj_dir / "project.json").write_text(json.dumps(data, indent=2))


def read_project(project_id: str) -> tuple[ProjectSpec, ProjectStatus]:
    """Read spec and status from project.json; raises FileNotFoundError if missing."""
    proj_file = get_project_dir(project_id) / "project.json"
    if not proj_file.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    data = json.loads(proj_file.read_text())
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


def write_page_sidecar(spec: ProjectSpec, idx: int, page_dict: dict[str, Any]) -> None:
    """Write a per-page JSON sidecar. Reads status to resolve page_name."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    pages_dir = _pages_dir(spec)
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"{page_name}.json").write_text(json.dumps(page_dict, indent=2))


def read_page_sidecar(spec: ProjectSpec, idx: int) -> dict[str, Any]:
    """Read a per-page JSON sidecar; raises FileNotFoundError if missing."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    sidecar_path = _pages_dir(spec) / f"{page_name}.json"
    if not sidecar_path.exists():
        raise FileNotFoundError(f"Sidecar not found for page {idx} in {spec.project_id}")
    # json.loads returns Any; caller validates the shape via Pydantic downstream
    return json.loads(sidecar_path.read_text())  # type: ignore[no-any-return]


def write_txt(spec: ProjectSpec, idx: int, text: str) -> None:
    """Write plain-text OCR output for one page."""
    _, status = read_project(spec.project_id)
    page_name = _page_name_for_idx(spec, status, idx)
    pages_dir = _pages_dir(spec)
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"{page_name}.txt").write_text(text)


def write_combined_txt(spec: ProjectSpec, status: ProjectStatus) -> None:
    """Concatenate all per-page .txt files into combined.txt."""
    pages_dir = _pages_dir(spec)
    parts: list[str] = []
    for page in sorted(status.pages, key=lambda p: p.page_idx):
        txt_path = pages_dir / f"{page.page_name}.txt"
        if txt_path.exists():
            parts.append(txt_path.read_text())
    combined = "\n\n".join(parts)
    (get_project_dir(spec.project_id) / "combined.txt").write_text(combined)


def list_projects() -> list[tuple[ProjectSpec, ProjectStatus]]:
    """Return all known projects from the projects root."""
    if not _PROJECTS_ROOT.exists():
        return []
    results: list[tuple[ProjectSpec, ProjectStatus]] = []
    for proj_dir in sorted(_PROJECTS_ROOT.iterdir()):
        proj_file = proj_dir / "project.json"
        if proj_file.exists():
            try:
                spec, status = read_project(proj_dir.name)
                results.append((spec, status))
            except Exception:  # noqa: BLE001, S110  # skip unreadable project dirs; listing must not fail
                pass
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
    )
    write_project(s, new_status)
