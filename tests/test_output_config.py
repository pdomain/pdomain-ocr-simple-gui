# tests/test_output_config.py
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.output.config import (
    OutputConfig,
    OutputConfigError,
    resolve_output_dir,
)
from pdomain_ocr_simple_gui.runtime.mode import Mode


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


@pytest.mark.parametrize("output_mode", ["specified", "next_to_source", "managed"])
@pytest.mark.parametrize("alias", ["direct", "parent-components", "symlink"])
def test_outputs_cannot_enter_the_removable_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_mode: str, alias: str
) -> None:
    import sys

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(sys, "prefix", str(runtime))
    unsafe = runtime / "saved-output"
    if alias == "parent-components":
        unsafe = tmp_path / "outside/../runtime/saved-output"
    elif alias == "symlink":
        link = tmp_path / "runtime-alias"
        link.symlink_to(runtime, target_is_directory=True)
        unsafe = link / "saved-output"
    cfg = OutputConfig.model_validate({"mode": output_mode, "path": str(unsafe)})
    with pytest.raises(OutputConfigError, match=r"outside.*installed"):
        _ = resolve_output_dir(
            cfg,
            mode=Mode.LOCAL,
            source_dir=unsafe,
            managed_root=unsafe,
            job_id="job1",
            source_is_folder=True,
        )
    assert sorted(runtime.iterdir()) == []


def test_global_python_allows_shared_writable_output_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    shared = tmp_path / "shared-python"
    monkeypatch.setattr(sys, "prefix", str(shared))
    monkeypatch.setattr(sys, "base_prefix", str(shared))
    target = shared / "workspace/output"
    result = resolve_output_dir(
        OutputConfig(mode="specified", path=target),
        mode=Mode.LOCAL,
        source_dir=tmp_path / "source",
        managed_root=tmp_path / "managed",
        job_id="job1",
        source_is_folder=True,
    )
    assert result == target
    assert target.is_dir()


@pytest.mark.parametrize("output_mode", ["specified", "next_to_source", "managed"])
def test_malformed_output_destination_has_a_domain_error(tmp_path: Path, output_mode: str) -> None:
    bad = tmp_path / "bad\0output"
    with pytest.raises(OutputConfigError, match="resolve"):
        _ = resolve_output_dir(
            OutputConfig.model_validate({"mode": output_mode, "path": str(bad)}),
            mode=Mode.LOCAL,
            source_dir=bad,
            managed_root=bad,
            job_id="job1",
            source_is_folder=True,
        )
    assert list(tmp_path.iterdir()) == []
