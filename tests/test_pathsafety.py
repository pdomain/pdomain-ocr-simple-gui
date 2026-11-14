"""Containment checks must work with Windows paths too.

Every check used ``str(path).startswith(str(root) + "/")``. Windows paths use
backslashes, so on Windows 11 every job id failed validation (GET /api/jobs/<id>
returned 400) and ZIP uploads would have been refused.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest

from pdomain_ocr_simple_gui.pathsafety import is_strictly_within

SRC = Path(__file__).resolve().parents[1] / "src" / "pdomain_ocr_simple_gui"


@pytest.mark.parametrize(
    ("candidate", "root", "expected"),
    [
        (
            PureWindowsPath(r"C:\Users\pdtest\AppData\projects\e611dc56"),
            PureWindowsPath(r"C:\Users\pdtest\AppData\projects"),
            True,
        ),
        (PureWindowsPath(r"C:\data\up\a\b.png"), PureWindowsPath(r"C:\data\up"), True),
        (PureWindowsPath(r"C:\data\up"), PureWindowsPath(r"C:\data\up"), False),
        (PureWindowsPath(r"C:\data\upx\b.png"), PureWindowsPath(r"C:\data\up"), False),
        (PureWindowsPath(r"D:\data\up\b.png"), PureWindowsPath(r"C:\data\up"), False),
        (PureWindowsPath(r"c:\data\UP\b.png"), PureWindowsPath(r"C:\Data\up"), True),
        (PureWindowsPath(r"\\host\share\up\b.png"), PureWindowsPath(r"\\host\share\up"), True),
        (PureWindowsPath(r"\\host\other\b.png"), PureWindowsPath(r"\\host\share\up"), False),
        (PureWindowsPath(r"C:evil.png"), PureWindowsPath(r"C:\data\up"), False),
        (PureWindowsPath(r"C:\a.png"), PureWindowsPath("C:\\"), True),
        (PurePosixPath("/srv/projects/abc"), PurePosixPath("/srv/projects"), True),
        (PurePosixPath("/a.png"), PurePosixPath("/"), True),
        (PurePosixPath("/srv/projects"), PurePosixPath("/srv/projects"), False),
        (PurePosixPath("/srv/projectsx/abc"), PurePosixPath("/srv/projects"), False),
        (PurePosixPath("/srv/abc"), PurePosixPath("/srv/projects"), False),
    ],
)
def test_is_strictly_within(candidate: PurePath, root: PurePath, expected: bool) -> None:
    assert is_strictly_within(candidate, root) is expected


def test_no_posix_only_containment_checks_remain() -> None:
    pattern = re.compile(r'\+\s*("/"|os\.sep)\)')
    offenders = [
        f"{path.relative_to(SRC)}:{n}"
        for path in SRC.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "startswith" in line and pattern.search(line)
    ]
    assert offenders == []
