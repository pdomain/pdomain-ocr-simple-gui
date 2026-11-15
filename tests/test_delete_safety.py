"""Deletion safety regressions for managed job output."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import get_project_dir, write_project


def _write_job(
    *,
    project_id: str,
    source_dir: Path,
    output_dir: Path,
    output_mode: str | None,
    meta_root: Path,
) -> None:
    now = datetime.now(UTC)
    spec = ProjectSpec(
        project_id=project_id,
        name="delete safety",
        source_path=str(source_dir),
        output_dir=str(output_dir),
        engine="doctr",
        language="en",
        created_at=now,
        last_opened_at=now,
    )
    status = ProjectStatus(
        project_id=project_id,
        state="succeeded",
        page_count=1,
        pages_done=1,
        pages=[PageResult(page_idx=0, page_name="page-001", state="succeeded")],
    )
    write_project(spec, status)
    if output_mode is not None:
        meta_dir = meta_root / project_id
        meta_dir.mkdir(parents=True)
        (meta_dir / "output_mode.json").write_text(json.dumps({"mode": output_mode}), encoding="utf-8")


async def _delete_job(project_id: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/jobs/{project_id}")
    assert response.status_code == 200


@pytest.fixture
def deletion_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    projects_root = tmp_path / "projects"
    output_root = tmp_path / "outputs"
    meta_root = tmp_path / "jobs_meta"
    for root in (projects_root, output_root, meta_root):
        root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT", str(meta_root))
    return projects_root, output_root, meta_root


@pytest.mark.parametrize("output_mode", ["next_to_source", "specified"])
async def test_delete_preserves_non_managed_output(
    deletion_roots: tuple[Path, Path, Path], output_mode: str
) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = f"keep-{output_mode}"
    output_dir = output_root / project_id
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=output_dir,
        output_mode=output_mode,
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_preserves_managed_mode_output_outside_managed_root(
    deletion_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = "outside-root"
    output_dir = tmp_path / "external" / project_id
    output_dir.mkdir(parents=True)
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=output_dir,
        output_mode="managed",
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_preserves_symlinked_managed_output(
    deletion_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = "symlink-output"
    external_dir = tmp_path / "external" / project_id
    external_dir.mkdir(parents=True)
    sentinel = external_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    output_dir = output_root / project_id
    output_dir.symlink_to(external_dir, target_is_directory=True)
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=output_dir,
        output_mode="managed",
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert output_dir.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_preserves_managed_root_symlink_target(deletion_roots: tuple[Path, Path, Path]) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = "managed-root-link"
    target_dir = output_root / "another-job"
    target_dir.mkdir()
    sentinel = target_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    (output_root / project_id).symlink_to(target_dir, target_is_directory=True)
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=target_dir,
        output_mode="managed",
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_preserves_output_below_symlinked_managed_root(
    deletion_roots: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, _, meta_root = deletion_roots
    project_id = "symlinked-root"
    external_root = tmp_path / "external-output-root"
    external_dir = external_root / project_id
    external_dir.mkdir(parents=True)
    sentinel = external_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    managed_root = tmp_path / "managed-output-root"
    managed_root.symlink_to(external_root, target_is_directory=True)
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(managed_root))
    _write_job(
        project_id=project_id,
        source_dir=external_root,
        output_dir=managed_root / project_id,
        output_mode="managed",
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_preserves_output_without_metadata(deletion_roots: tuple[Path, Path, Path]) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = "missing-metadata"
    output_dir = output_root / project_id
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=output_dir,
        output_mode=None,
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


async def test_delete_never_removes_managed_output_root(deletion_roots: tuple[Path, Path, Path]) -> None:
    _, output_root, meta_root = deletion_roots
    project_id = "output-root"
    sentinel = output_root / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    _write_job(
        project_id=project_id,
        source_dir=output_root,
        output_dir=output_root,
        output_mode="managed",
        meta_root=meta_root,
    )

    await _delete_job(project_id)

    assert not get_project_dir(project_id).exists()
    assert not (meta_root / project_id).exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"
