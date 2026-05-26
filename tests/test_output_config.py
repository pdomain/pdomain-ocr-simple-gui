# tests/test_output_config.py
from pathlib import Path

import pytest

from pd_ocr_simple_gui.output.config import (
    OutputConfig,
    OutputConfigError,
    resolve_output_dir,
)
from pd_ocr_simple_gui.runtime.mode import Mode


def test_managed_default(tmp_path: Path) -> None:
    cfg = OutputConfig(mode="managed")
    resolved = resolve_output_dir(
        cfg,
        mode=Mode.LOCAL,
        source_dir=tmp_path / "src",
        managed_root=tmp_path / "out",
        job_id="job1",
        source_is_folder=False,
    )
    assert resolved == tmp_path / "out" / "job1"
    assert resolved.is_dir()


def test_next_to_source_folder(tmp_path: Path) -> None:
    cfg = OutputConfig(mode="next_to_source")
    src = tmp_path / "src"
    src.mkdir()
    resolved = resolve_output_dir(
        cfg,
        mode=Mode.LOCAL,
        source_dir=src,
        managed_root=tmp_path / "out",
        job_id="job1",
        source_is_folder=True,
    )
    assert resolved == src


def test_next_to_source_rejects_non_folder(tmp_path: Path) -> None:
    cfg = OutputConfig(mode="next_to_source")
    with pytest.raises(OutputConfigError):
        resolve_output_dir(
            cfg,
            mode=Mode.LOCAL,
            source_dir=tmp_path / "src",
            managed_root=tmp_path / "out",
            job_id="job1",
            source_is_folder=False,
        )


def test_specified_local(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    cfg = OutputConfig(mode="specified", path=target)
    resolved = resolve_output_dir(
        cfg,
        mode=Mode.LOCAL,
        source_dir=tmp_path,
        managed_root=tmp_path / "out",
        job_id="job1",
        source_is_folder=True,
    )
    assert resolved == target


def test_specified_rejected_in_managed(tmp_path: Path) -> None:
    cfg = OutputConfig(mode="specified", path=tmp_path)
    with pytest.raises(OutputConfigError):
        resolve_output_dir(
            cfg,
            mode=Mode.MANAGED,
            source_dir=tmp_path,
            managed_root=tmp_path / "out",
            job_id="job1",
            source_is_folder=True,
        )
