"""Tests that setup tooling does not assume the old devcontainer or GitHub owner."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _clean_env() -> dict[str, str]:
    dropped = {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "PLAYWRIGHT_BROWSERS_PATH"}
    return {k: v for k, v in os.environ.items() if k not in dropped and not k.startswith("GIT_")}


def test_make_recipes_leave_the_playwright_browser_path_unset() -> None:
    result = subprocess.run(
        ["make", "-n", "setup", "e2e-fast", "e2e-browser", "e2e-real-ocr"],
        cwd=REPO_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "playwright install chromium" in result.stdout
    assert "PLAYWRIGHT_BROWSERS_PATH" not in result.stdout


def test_local_setup_clones_siblings_from_the_pdomain_org(tmp_path: Path) -> None:
    workspace = tmp_path.resolve() / "workspace"
    repo = workspace / "pdomain-ocr-simple-gui"
    (repo / "scripts").mkdir(parents=True)
    script = repo / "scripts" / "local-setup.sh"
    _ = shutil.copy(REPO_ROOT / "scripts" / "local-setup.sh", script)
    env = _clean_env()
    _ = subprocess.run(["git", "init", "--quiet"], cwd=repo, env=env, check=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_log = tmp_path / "gh.log"
    fake_gh = bin_dir / "gh"
    _ = fake_gh.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{gh_log}"\n')
    fake_gh.chmod(0o755)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    _ = subprocess.run(["bash", str(script)], cwd=repo, env=env, capture_output=True, check=True)

    clones = [line for line in gh_log.read_text().splitlines() if line.startswith("repo clone ")]
    assert clones == [
        f"repo clone pdomain/{sibling} {workspace / sibling}"
        for sibling in ("pdomain-book-tools", "pdomain-ops", "pdomain-ui")
    ]
