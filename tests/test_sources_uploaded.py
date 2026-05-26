# tests/test_sources_uploaded.py
from pathlib import Path

import pytest

from pd_ocr_simple_gui.sources import SourceNotFound
from pd_ocr_simple_gui.sources.uploaded_files import UploadedFilesSource


def test_happy_path(tmp_path: Path) -> None:
    stage = tmp_path / "upload-abc"
    stage.mkdir()
    (stage / "scan.png").write_bytes(b"\x89PNG")
    assert UploadedFilesSource("abc", root=tmp_path).materialize() == stage


def test_missing(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFound):
        UploadedFilesSource("nope", root=tmp_path).materialize()
