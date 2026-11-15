"""The macOS installer distinguishes user cancellation from dialog failures."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (1, "execution error: User canceled. (-128)", 0),
        (1, "Not authorized to send Apple events", 1),
        (2, "Dialog could not start", 2),
    ],
)
def test_initial_confirmation_preserves_real_errors(
    tmp_path: Path, status: int, message: str, expected: int
) -> None:
    root = Path(__file__).resolve().parents[1]
    fake = tmp_path / "osascript"
    _ = fake.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_OSA_MESSAGE" >&2\nexit "$FAKE_OSA_STATUS"\n')
    fake.chmod(0o755)
    source = (root / "installer/macos/install-native.sh").read_text()
    script = tmp_path / "install-native.sh"
    _ = script.write_text(source.replace("/usr/bin/osascript", str(fake)))
    forbidden = tmp_path / "install-called"
    _ = (tmp_path / "install.sh").write_text(f'touch "{forbidden}"\nexit 93\n')
    result = subprocess.run(
        ["/bin/sh", str(script)],
        env={
            **os.environ,
            "TMPDIR": str(tmp_path),
            "FAKE_OSA_MESSAGE": message,
            "FAKE_OSA_STATUS": str(status),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected, result.stderr
    assert not forbidden.exists()
    if expected:
        assert message in result.stderr
