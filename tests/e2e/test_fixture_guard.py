"""Tests for the _assert_under_tmp guard in e2e conftest."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestAssertUnderTmp:
    """_assert_under_tmp must raise RuntimeError for paths outside the tmp root."""

    def test_raises_for_path_outside_tmp(self, tmp_path: Path) -> None:
        """A real system path (not under tmp_path) raises RuntimeError."""
        from tests.e2e.conftest import _assert_under_tmp

        with pytest.raises(RuntimeError, match="refusing to write outside tmpdir"):
            _assert_under_tmp(Path("/home/vscode/real-root"), tmp_path)

    def test_passes_for_path_inside_tmp(self, tmp_path: Path) -> None:
        """A path directly under tmp_path does not raise."""
        from tests.e2e.conftest import _assert_under_tmp

        subdir = tmp_path / "subdir"
        _assert_under_tmp(subdir, tmp_path)  # must not raise

    def test_passes_for_tmp_root_itself(self, tmp_path: Path) -> None:
        """The tmp_path itself (exact match) does not raise."""
        from tests.e2e.conftest import _assert_under_tmp

        _assert_under_tmp(tmp_path, tmp_path)  # must not raise

    def test_raises_for_parent_of_tmp(self, tmp_path: Path) -> None:
        """A path that is a parent of tmp_path raises RuntimeError."""
        from tests.e2e.conftest import _assert_under_tmp

        parent = tmp_path.parent
        with pytest.raises(RuntimeError, match="refusing to write outside tmpdir"):
            _assert_under_tmp(parent, tmp_path)
