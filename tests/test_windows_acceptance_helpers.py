"""Pure helpers of scripts/windows_acceptance.py; no browser and no server."""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

import pytest

from scripts.windows_acceptance import (
    AcceptanceError,
    job_id_from_url,
    normalise_newlines,
    resolve_fixtures,
    word_overlap,
    zip_text_files,
)

if TYPE_CHECKING:
    from pathlib import Path


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_word_overlap_ignores_case_and_punctuation() -> None:
    assert word_overlap("The quick, brown FOX.", "the quick brown fox") == 1.0


def test_word_overlap_is_partial_and_safe_on_empty_truth() -> None:
    assert word_overlap("quick fox", "quick brown fox jumps") == 0.5
    assert word_overlap("anything", "") == 0.0


def test_normalise_newlines_turns_crlf_into_lf_only() -> None:
    assert normalise_newlines("a\r\nb\nc\r") == "a\nb\nc\r"


def test_zip_text_files_normalises_crlf_and_reports_names() -> None:
    data = _zip({"p.txt": b"one\r\ntwo", "p.json": b'{"a": 1}', "p.png": b"\x89PNG", "all.txt": b"x\ny"})
    texts = zip_text_files(data)
    assert texts.files == {"p.txt": "one\ntwo", "p.json": '{"a": 1}', "all.txt": "x\ny"}
    assert texts.crlf_names == ("p.txt",)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8004/jobs/abc-123", "abc-123"),
        ("http://127.0.0.1:8004/jobs/abc-123?tab=x#top", "abc-123"),
        ("http://127.0.0.1:8004/", None),
    ],
)
def test_job_id_from_url(url: str, expected: str | None) -> None:
    assert job_id_from_url(url) == expected


def test_resolve_fixtures_accepts_directory_image_and_truth_file(tmp_path: Path) -> None:
    _ = (tmp_path / "other.png").write_bytes(b"")
    _ = (tmp_path / "other.gt.txt").write_text("x", encoding="utf-8")
    for given in (tmp_path, tmp_path / "other.png", tmp_path / "other.gt.txt"):
        fixture = resolve_fixtures(given)
        assert fixture.image.name == "other.png"
        assert fixture.truth.name == "other.gt.txt"
        assert fixture.stem == "other"


def test_resolve_fixtures_rejects_missing_truth(tmp_path: Path) -> None:
    _ = (tmp_path / "lonely.png").write_bytes(b"")
    with pytest.raises(AcceptanceError):
        _ = resolve_fixtures(tmp_path)
