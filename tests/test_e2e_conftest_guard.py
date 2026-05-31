"""Tests for the PD_SUITE_DATA_DIR safety guard in the e2e conftest.

The guard in _boot_server (tests/e2e/conftest.py) must raise AssertionError
when PD_SUITE_DATA_DIR is absent or points outside a tmp directory, preventing
the prefs-reset autouse fixture from overwriting real user data.
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import _assert_suite_data_dir_is_tmp


@pytest.mark.parametrize(
    ("value", "should_pass"),
    [
        # Absent / empty — must raise
        ("", False),
        # Real user dir — must raise
        ("/home/user/.local/share", False),
        ("/root", False),
        # Tmp-like paths — must pass
        ("/tmp/pytest-123/e2e_server_data0", True),
        ("/tmp/e2e_root", True),
    ],
    ids=["empty", "home", "root", "tmp-pytest", "tmp-plain"],
)
def test_suite_data_dir_guard(value: str, should_pass: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """_assert_suite_data_dir_is_tmp passes for tmp paths and raises for others."""
    if should_pass:
        _assert_suite_data_dir_is_tmp(value)  # must not raise
    else:
        with pytest.raises(AssertionError, match="PD_SUITE_DATA_DIR"):
            _assert_suite_data_dir_is_tmp(value)
