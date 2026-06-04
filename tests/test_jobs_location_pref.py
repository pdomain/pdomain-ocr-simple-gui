"""Tests for the jobs-location preference and projects-root precedence.

Precedence under test: env > pref > default. The autouse storage-isolation
guard in ``tests/conftest.py`` sets the projects-root env var to a session
tmpdir, so the pref branch must explicitly ``delenv`` that var AND point the
pref at a tmp path so the guard never sees a real-home resolution.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.storage import _projects_root

_ENV_VAR = "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"


def _adapter_with_jobs_location(value: str) -> MagicMock:
    """Build a mock prefs adapter whose stored AppPrefs has jobs_location=value."""
    from pdomain_ops.suite.types import UIPrefs

    mock = MagicMock()
    ui_prefs = UIPrefs()
    ui_prefs.apps["pdomain-ocr-simple-gui"] = {"jobs_location": value}
    mock.read.return_value = ui_prefs
    mock.write_app.return_value = None
    return mock


class TestProjectsRootPrecedence:
    def test_env_wins_over_pref(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When the env var is set AND a pref is set, the env var wins."""
        import pdomain_ocr_simple_gui.app as app_mod

        env_root = tmp_path / "env_projects"
        env_root.mkdir()
        pref_root = tmp_path / "pref_projects"
        pref_root.mkdir()
        monkeypatch.setenv(_ENV_VAR, str(env_root))
        monkeypatch.setattr(app_mod, "_prefs_adapter", _adapter_with_jobs_location(str(pref_root)))

        assert _projects_root() == env_root

    def test_pref_used_when_env_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env unset + pref set (pointing at tmp) → the pref location is used.

        Must delenv the projects-root var (the autouse guard sets it) and point
        the pref at a tmp dir so resolution never escapes the pytest tmp tree.
        """
        import pdomain_ocr_simple_gui.app as app_mod

        pref_root = tmp_path / "pref_projects"
        pref_root.mkdir()
        monkeypatch.delenv(_ENV_VAR, raising=False)
        monkeypatch.setattr(app_mod, "_prefs_adapter", _adapter_with_jobs_location(str(pref_root)))

        assert _projects_root() == pref_root.resolve()

    def test_pref_expands_user_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pref value with a leading ~ is expanded to the user home."""
        import pdomain_ocr_simple_gui.app as app_mod

        monkeypatch.delenv(_ENV_VAR, raising=False)
        monkeypatch.setattr(app_mod, "_prefs_adapter", _adapter_with_jobs_location("~/sub/jobs"))

        assert _projects_root() == (Path.home() / "sub" / "jobs").resolve()

    def test_default_when_both_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env unset + pref empty → the shipped default is used."""
        import pdomain_ocr_simple_gui.app as app_mod
        from pdomain_ocr_simple_gui.storage import _PROJECTS_ROOT_DEFAULT

        monkeypatch.delenv(_ENV_VAR, raising=False)
        monkeypatch.setattr(app_mod, "_prefs_adapter", _adapter_with_jobs_location(""))

        assert _projects_root() == _PROJECTS_ROOT_DEFAULT

    def test_default_when_no_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env unset + no adapter → the shipped default is used."""
        import pdomain_ocr_simple_gui.app as app_mod
        from pdomain_ocr_simple_gui.storage import _PROJECTS_ROOT_DEFAULT

        monkeypatch.delenv(_ENV_VAR, raising=False)
        monkeypatch.setattr(app_mod, "_prefs_adapter", None)

        assert _projects_root() == _PROJECTS_ROOT_DEFAULT


class TestPutPrefsJobsLocationValidation:
    async def test_valid_writable_location_persists_and_round_trips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A writable jobs_location is accepted (200) and round-trips on GET."""
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        target = tmp_path / "new_jobs"
        store: dict[str, dict[str, object]] = {}
        mock = MagicMock()
        ui_prefs = UIPrefs()
        ui_prefs.apps = store  # type: ignore[assignment]
        mock.read.return_value = ui_prefs

        def _write_app(app_id: str, data: dict[str, object]) -> None:
            store[app_id] = data

        mock.write_app.side_effect = _write_app
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            put = await ac.put("/api/prefs", json={"jobs_location": str(target)})
            assert put.status_code == 200, put.text
            assert put.json()["jobs_location"] == str(target)
            # mkdir happened as part of validation
            assert target.is_dir()
            get = await ac.get("/api/prefs")
            assert get.status_code == 200
            assert get.json()["jobs_location"] == str(target)

    async def test_empty_location_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty jobs_location is always accepted (means: env/default)."""
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/api/prefs", json={"jobs_location": ""})
        assert resp.status_code == 200
        assert resp.json()["jobs_location"] == ""

    async def test_non_writable_location_returns_400(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A jobs_location that cannot be created/written returns 400 + message."""
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)

        # A regular file used as a parent dir → mkdir(parents=True) fails.
        blocker = tmp_path / "iam_a_file"
        blocker.write_text("x")
        bad = blocker / "child" / "jobs"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/api/prefs", json={"jobs_location": str(bad)})
        assert resp.status_code == 400
        assert "jobs location" in resp.json()["detail"].lower()


class TestJobsLocationIntegration:
    def test_job_written_and_listed_under_pref_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With env unset and a tmp pref root, storage writes/lists under it."""
        from datetime import UTC, datetime

        import pdomain_ocr_simple_gui.app as app_mod
        from pdomain_ocr_simple_gui.models import ProjectSpec, ProjectStatus
        from pdomain_ocr_simple_gui.storage import (
            get_project_dir,
            list_projects,
            write_project,
        )

        pref_root = tmp_path / "pref_projects"
        pref_root.mkdir()
        monkeypatch.delenv(_ENV_VAR, raising=False)
        monkeypatch.setattr(app_mod, "_prefs_adapter", _adapter_with_jobs_location(str(pref_root)))

        spec = ProjectSpec(
            project_id="integ-proj-001",
            name="Integration",
            source_path=str(tmp_path / "src"),
            output_dir=str(tmp_path / "out"),
            engine="doctr",
            language="en",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        status = ProjectStatus(
            project_id="integ-proj-001",
            state="succeeded",
            page_count=0,
            pages_done=0,
            pages=[],
        )
        write_project(spec, status)

        assert get_project_dir("integ-proj-001").parent == pref_root.resolve()
        assert (pref_root.resolve() / "integ-proj-001" / "project.json").exists()
        listed = [s.project_id for s, _ in list_projects()]
        assert "integ-proj-001" in listed
