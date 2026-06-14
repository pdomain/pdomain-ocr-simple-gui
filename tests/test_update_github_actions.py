from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATER_PATH = ROOT / "scripts" / "update_github_actions.py"
spec = importlib.util.spec_from_file_location("update_github_actions", UPDATER_PATH)
assert spec is not None
assert spec.loader is not None
update_github_actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_github_actions)


def test_detects_unmanaged_workflow_action(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: ci\njobs:\n  ci:\n    steps:\n      - uses: example/not-managed@abc123\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="example/not-managed"):
        update_github_actions.verify_managed_actions(workflows)


def test_accepts_local_workflow_call(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release.yml").write_text(
        "jobs:\n  regen:\n    uses: ./.github/workflows/regen.yml\n",
        encoding="utf-8",
    )

    update_github_actions.verify_managed_actions(workflows)


def test_accepts_quoted_managed_actions_and_local_workflows(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "jobs:\n"
        "  ci:\n"
        "    steps:\n"
        '      - uses: "actions/checkout@abc123"\n'
        "      - uses: './.github/workflows/regen.yml'\n",
        encoding="utf-8",
    )

    update_github_actions.verify_managed_actions(workflows)


def test_current_workflows_use_only_managed_actions() -> None:
    update_github_actions.verify_managed_actions()


def test_update_workflow_refs_updates_quoted_action_refs(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "jobs:\n"
        "  ci:\n"
        "    steps:\n"
        '      - uses: "actions/checkout@oldoldoldoldoldoldoldoldoldoldoldoldoldoldoldoldold1"\n'
        "      - uses: 'astral-sh/setup-uv@oldoldoldoldoldoldoldoldoldoldoldoldoldoldoldoldold2'\n",
        encoding="utf-8",
    )
    releases = {
        "actions/checkout": update_github_actions.ActionRelease(tag="v-test", sha="a" * 40),
        "astral-sh/setup-uv": update_github_actions.ActionRelease(tag="v-test", sha="b" * 40),
    }

    assert update_github_actions.update_workflow_refs(workflow, releases=releases)
    text = workflow.read_text(encoding="utf-8")
    assert f'uses: "actions/checkout@{"a" * 40}"' in text
    assert f"uses: 'astral-sh/setup-uv@{'b' * 40}'" in text


def test_update_uv_version_refs_updates_quoted_setup_uv(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "jobs:\n"
        "  ci:\n"
        "    steps:\n"
        '      - uses: "astral-sh/setup-uv@oldoldoldoldoldoldoldoldoldoldoldoldoldoldoldoldold2"\n'
        "        with:\n"
        '          version: "0.1.0"\n',
        encoding="utf-8",
    )

    assert update_github_actions.update_uv_version_refs(workflow, version="0.11.16")
    assert 'version: "0.11.16"' in workflow.read_text(encoding="utf-8")


def test_update_uv_version_refs_updates_quoted_setup_uv_with_inline_comment(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "jobs:\n"
        "  ci:\n"
        "    steps:\n"
        '      - uses: "astral-sh/setup-uv@oldoldoldoldoldoldoldoldoldoldoldoldoldoldoldoldold2"  # v8.1.0\n'
        "        with:\n"
        '          version: "0.1.0"\n',
        encoding="utf-8",
    )

    assert update_github_actions.update_uv_version_refs(workflow, version="0.11.16")
    assert 'version: "0.11.16"' in workflow.read_text(encoding="utf-8")


def _make_fake_runner(uv_version: str = "0.99.0", sha: str = "a" * 40):  # type: ignore[no-untyped-def]
    """Return a fake GhRunner that doesn't hit the network."""

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        endpoint = command[-1]
        if endpoint.endswith("/releases/latest") and "astral-sh/uv" in endpoint:
            payload: dict[str, object] = {"tag_name": uv_version}
        elif endpoint.endswith("/releases/latest"):
            payload = {"tag_name": "v-test"}
        elif "/git/ref/tags/" in endpoint:
            payload = {"object": {"type": "commit", "sha": sha}}
        else:
            payload = {}
        return subprocess.CompletedProcess(args=command, returncode=0, stdout=json.dumps(payload), stderr="")

    return fake_runner


def test_update_github_actions_does_not_touch_pyproject(tmp_path: Path) -> None:
    """update_github_actions() must never write pyproject.toml.

    The dep-refresh job runs ``uv lock --upgrade`` after the script, but uv
    enforces ``required-version`` before doing any work.  If the script pins
    required-version to the *latest* release, the job's older pinned uv
    (installed by setup-uv at job start) immediately violates the requirement
    it just wrote — self-poisoning the run.  The required-version floor is a
    deliberate contributor floor; only humans bump it.
    """
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "jobs:\n"
        "  ci:\n"
        "    steps:\n"
        '      - uses: "actions/checkout@oldoldoldoldoldoldoldoldoldoldoldoldoldoldoldoldold1"\n',
        encoding="utf-8",
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.uv]\nrequired-version = ">=0.11.16"\n', encoding="utf-8")
    original_pyproject = pyproject.read_text(encoding="utf-8")

    changed = update_github_actions.update_github_actions(
        workflow_dir=workflows,
        pyproject=pyproject,
        runner=_make_fake_runner(),
    )

    assert pyproject.read_text(encoding="utf-8") == original_pyproject, (
        "update_github_actions() must not modify pyproject.toml"
    )
    assert pyproject not in changed, "pyproject.toml must not appear in the changed-paths list"


def test_update_pyproject_uv_version_function_removed() -> None:
    """The update_pyproject_uv_version function must not exist in the module.

    Its removal was the fix for the dep-refresh self-poison bug where the
    script pinned required-version to the latest uv release, causing the
    dep-refresh job's older pinned uv to violate the requirement it just wrote.
    """
    assert not hasattr(update_github_actions, "update_pyproject_uv_version"), (
        "update_pyproject_uv_version must be removed from update_github_actions.py"
    )
