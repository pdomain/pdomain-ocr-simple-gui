from pathlib import Path

import pytest

from pd_ocr_simple_gui.sources import SourceInvalid, SourceNotFound
from pd_ocr_simple_gui.sources.local_path import LocalPathSource


def test_folder_happy_path(tmp_path: Path) -> None:
    (tmp_path / "page-001.png").write_bytes(b"fake-png")
    src = LocalPathSource(tmp_path)
    assert src.materialize() == tmp_path


def test_missing_path(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFound):
        LocalPathSource(tmp_path / "nope").materialize()


def test_unreadable_file(tmp_path: Path) -> None:
    target = tmp_path / "weird"
    target.write_text("not an image")
    with pytest.raises(SourceInvalid):
        LocalPathSource(target).materialize()


def test_single_image_path(tmp_path: Path) -> None:
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n")
    src = LocalPathSource(img)
    materialized = src.materialize()
    assert materialized.is_dir()
    assert (materialized / img.name).exists()
