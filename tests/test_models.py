"""Tests for pdomain_ocr_simple_gui.models — round-trip JSON and field validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pdomain_ocr_simple_gui.models import AppPrefs, PageResult, ProjectSpec, ProjectStatus


def _make_spec(**overrides: object) -> ProjectSpec:
    defaults: dict[str, object] = {
        "project_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "name": "My Project",
        "source_path": "/tmp/imgs",
        "output_dir": "/tmp/out",
        "engine": "doctr",
        "language": "en",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_opened_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ProjectSpec(**defaults)  # type: ignore[arg-type]


class TestProjectSpec:
    def test_round_trip_json(self) -> None:
        spec = _make_spec()
        restored = ProjectSpec.model_validate_json(spec.model_dump_json())
        assert restored == spec

    def test_defaults(self) -> None:
        spec = _make_spec()
        assert spec.save_json is False
        assert spec.combined_txt is True

    def test_engine_literal(self) -> None:
        with pytest.raises(ValidationError):
            _make_spec(engine="unknown-engine")

    def test_tesseract_engine(self) -> None:
        spec = _make_spec(engine="tesseract")
        assert spec.engine == "tesseract"


class TestPageResult:
    def test_defaults(self) -> None:
        pr = PageResult(page_idx=0, page_name="page_001.png", state="queued")
        assert pr.text_preview == ""
        assert pr.error is None

    def test_round_trip(self) -> None:
        pr = PageResult(page_idx=2, page_name="page_003.png", state="succeeded", text_preview="Hello world")
        restored = PageResult.model_validate_json(pr.model_dump_json())
        assert restored == pr

    def test_state_literal(self) -> None:
        with pytest.raises(ValidationError):
            PageResult(page_idx=0, page_name="x.png", state="pending")


class TestProjectStatus:
    def test_round_trip(self) -> None:
        status = ProjectStatus(
            project_id="abc",
            state="running",
            page_count=3,
            pages_done=1,
            pages=[
                PageResult(page_idx=0, page_name="a.png", state="succeeded"),
                PageResult(page_idx=1, page_name="b.png", state="running"),
                PageResult(page_idx=2, page_name="c.png", state="queued"),
            ],
        )
        restored = ProjectStatus.model_validate_json(status.model_dump_json())
        assert restored == status


class TestAppPrefs:
    def test_defaults(self) -> None:
        prefs = AppPrefs()
        assert prefs.default_engine == "doctr"
        assert prefs.default_language == "en"
        assert prefs.save_json_default is False
        assert prefs.combined_txt_default is True
        assert prefs.recent_projects == []

    def test_round_trip(self) -> None:
        prefs = AppPrefs(
            default_engine="tesseract",
            default_language="fr",
            default_output_dir="/home/user/ocr",
            recent_projects=[{"project_id": "x", "name": "Test"}],
        )
        restored = AppPrefs.model_validate_json(prefs.model_dump_json())
        assert restored == prefs
