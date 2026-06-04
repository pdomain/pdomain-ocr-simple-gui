"""Tests that the session-wide storage isolation guard in conftest.py is active.

Verifies that after the autouse ``_isolate_storage_roots`` fixture runs,
``storage._projects_root()`` does NOT resolve to the real production default path,
and that ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT`` is set in the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui import storage
from tests.conftest import _assert_roots_under_tmp, _is_under_tmp_tree


class TestIsUnderTmpTree:
    """_is_under_tmp_tree — the predicate the session guard uses."""

    def test_path_under_session_root_is_accepted(self, tmp_path: Path) -> None:
        """A path under a provided pytest tmp root is recognised."""
        assert _is_under_tmp_tree(tmp_path / "projects", tmp_path) is True

    def test_real_home_path_is_rejected(self) -> None:
        """The real home-dir storage path must NOT pass the guard."""
        real = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"
        assert _is_under_tmp_tree(real) is False

    def test_arbitrary_tmp_path_is_accepted(self) -> None:
        """A bare /tmp/... path is accepted by the segment fallback."""
        assert _is_under_tmp_tree(Path("/tmp/pytest-of-vscode/pytest-1/x")) is True


class TestAssertRootsUnderTmp:
    """_assert_roots_under_tmp — the fail-closed mechanism the fixture invokes.

    The predicate above only proves _is_under_tmp_tree returns False for a
    home path; these tests prove the GUARD ITSELF fires (raises) when a data
    root escapes the tmp tree — exercising the same raise path the autouse
    ``_isolate_storage_roots`` fixture relies on at conftest.py.
    """

    def test_raises_when_root_points_at_real_home(self, tmp_path: Path) -> None:
        """A data root at the real home-dir storage must raise RuntimeError."""
        real_home = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"
        env = {"PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(real_home)}
        with pytest.raises(RuntimeError, match="Storage-isolation guard"):
            _assert_roots_under_tmp(env, tmp_path)

    def test_error_names_the_offending_var(self, tmp_path: Path) -> None:
        """The raised error must identify which var leaked, for fast triage."""
        real_home = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "outputs"
        env = {"PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(real_home)}
        with pytest.raises(RuntimeError) as excinfo:
            _assert_roots_under_tmp(env, tmp_path)
        assert "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT" in str(excinfo.value)

    def test_does_not_raise_when_all_roots_under_tmp(self, tmp_path: Path) -> None:
        """A root inside the provided tmp tree must pass without raising."""
        env = {"PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(tmp_path / "projects")}
        # Must not raise.
        _assert_roots_under_tmp(env, tmp_path)

    def test_ignores_unset_and_empty_vars(self, tmp_path: Path) -> None:
        """Unset / empty vars are skipped — only set escaping roots trip it."""
        env = {"PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": ""}
        # Empty value is ignored; no raise.
        _assert_roots_under_tmp(env, tmp_path)


def test_projects_root_is_not_real_home_default() -> None:
    """_projects_root() must NOT be the real home-dir production default.

    This passes only when the session-wide isolation guard has fired and
    PD_OCR_SIMPLE_GUI_PROJECTS_ROOT is set to a tmp path.  If the guard is
    absent or broken the root resolves to the real data directory and this
    test fails.
    """
    real_default = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"
    actual = storage._projects_root()
    assert actual != real_default, (
        f"_projects_root() returned the real production path {actual!r}. "
        "The session-wide isolation guard in tests/conftest.py is not active."
    )


def test_projects_root_env_var_is_set() -> None:
    """PD_OCR_SIMPLE_GUI_PROJECTS_ROOT must be set in the environment.

    Confirms the session guard set the env var before this test ran.
    """
    var = "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT"
    assert var in os.environ, (
        f"{var} is not set — the session-wide isolation guard in tests/conftest.py is not active."
    )


def test_projects_root_resolves_under_tmp() -> None:
    """_projects_root() must resolve under a pytest tmp dir.

    pytest places session tmps under /tmp/pytest-* (Linux) or the OS temp dir.
    This assertion checks for 'pytest' in the path without hard-coding the exact
    OS prefix.
    """
    actual = storage._projects_root().resolve()
    path_str = str(actual)
    assert "pytest" in path_str or path_str.startswith("/tmp"), (
        f"_projects_root() resolved to {actual!r} which does not look like a pytest tmpdir. "
        "The session-wide isolation guard may have been bypassed."
    )
