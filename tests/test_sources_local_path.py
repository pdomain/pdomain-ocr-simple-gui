import zipfile
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.sources import SourceInvalid, SourceNotFound, SourceTooLarge
from pdomain_ocr_simple_gui.sources.local_path import LocalPathSource


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


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_zip_happy_path(tmp_path: Path) -> None:
    zpath = tmp_path / "scans.zip"
    _make_zip(zpath, {"a.png": b"\x89PNG", "b.png": b"\x89PNG"})
    materialized = LocalPathSource(zpath, extract_root=tmp_path).materialize()
    assert (materialized / "a.png").exists()
    assert (materialized / "b.png").exists()


def test_zip_bomb_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pdomain_ocr_simple_gui.sources.local_path._MAX_UNCOMPRESSED_BYTES", 16)
    zpath = tmp_path / "bomb.zip"
    _make_zip(zpath, {"big.bin": b"A" * 1024})
    with pytest.raises(SourceTooLarge):
        LocalPathSource(zpath, extract_root=tmp_path).materialize()


def test_zip_traversal_blocked(tmp_path: Path) -> None:
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../escape.png", b"x")
    with pytest.raises(SourceInvalid):
        LocalPathSource(zpath, extract_root=tmp_path).materialize()
