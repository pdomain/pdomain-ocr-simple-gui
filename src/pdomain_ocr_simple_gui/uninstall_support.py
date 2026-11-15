"""Prepare and finalize conservative native uninstalls."""

from __future__ import annotations

import base64
import contextlib
import csv
import json
import os
import re
import shutil
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Protocol

    class _Locations(Protocol):
        @property
        def config_root(self) -> Path: ...
        @property
        def data_root(self) -> Path: ...
        @property
        def state_root(self) -> Path: ...
        @property
        def cache_root(self) -> Path: ...
        @property
        def projects_root(self) -> Path: ...
        @property
        def uploads_root(self) -> Path: ...
        @property
        def outputs_root(self) -> Path: ...
        @property
        def jobs_root(self) -> Path: ...
        @property
        def overrides(self) -> Mapping[str, str]: ...


APP_ID = "pdomain-ocr-simple-gui"
_KNOWN_FILES = ("installed.toml", "ui-prefs.json")
_UV_TOOL_CONTROL_FILES = frozenset({".gitignore", ".lock"})


@dataclass(frozen=True)
class CleanupAction:
    """One known shared-file operation."""

    kind: Literal["delete_file", "remove_empty_dir"]
    path: str


@dataclass(frozen=True)
class CleanupPlan:
    """A conservative post-removal suite cleanup decision."""

    suite_root: str
    tools_root: str
    own_environment: str
    safe_to_execute: bool
    reason: str
    actions: tuple[CleanupAction, ...]
    finalize_script: str = ""
    uninstall_marker: str = ""
    operation_token: str = ""

    def to_json(self) -> dict[str, object]:
        """Serialize the plan for a native wrapper."""
        return {**asdict(self), "actions": [asdict(action) for action in self.actions]}


class UninstallPreparationError(RuntimeError):
    """The native wrapper must preserve its controls after this error."""


def _unsafe(suite_root: Path, tools_root: Path, own_environment: Path, reason: str) -> CleanupPlan:
    return CleanupPlan(str(suite_root), str(tools_root), str(own_environment), False, reason, ())


def _registry_has_other(suite_root: Path) -> bool | None:
    path = suite_root / "installed.toml"
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
        _ = tomllib.loads(text)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    lines = tuple(text.splitlines())
    app_sections = tuple(line.strip() for line in lines if line.strip().startswith("[apps."))
    if any(not section.endswith("]") or section.count("[") != 1 for section in app_sections):
        return None
    return any(section not in {f"[apps.{APP_ID}]", f'[apps."{APP_ID}"]'} for section in app_sections)


def _environment_owns_suite(environment: Path) -> bool | None:
    if environment.is_symlink() or not (environment / "pyvenv.cfg").is_file():
        return None
    try:
        distributions = tuple(environment.rglob("*.dist-info"))
    except OSError:
        return None
    if not distributions:
        return None
    owns_suite = False
    for distribution in distributions:
        record = distribution / "RECORD"
        if (
            not distribution.is_dir()
            or distribution.is_symlink()
            or not record.is_file()
            or record.is_symlink()
        ):
            return None
        try:
            with record.open(encoding="utf-8", newline="") as stream:
                owns_suite = owns_suite or any(
                    row and Path(row[0]).name == "pdomain-suite.json" for row in csv.reader(stream)
                )
        except OSError:
            return None
        direct_url = distribution / "direct_url.json"
        if direct_url.exists():
            return None
    try:
        return None if tuple(environment.rglob("__editable__*.pth")) else owns_suite
    except OSError:
        return None


def plan_suite_cleanup(*, suite_root: Path, tools_root: Path, own_environment: Path) -> CleanupPlan:
    """Plan only known integration cleanup after a complete ownership scan."""
    registered = _registry_has_other(suite_root)
    if registered is None:
        return _unsafe(suite_root, tools_root, own_environment, "unreadable_registry")
    if registered:
        return _unsafe(suite_root, tools_root, own_environment, "other_suite_app_registered")
    if tools_root.exists() and not tools_root.is_dir():
        return _unsafe(suite_root, tools_root, own_environment, "unreadable_tool_inventory")
    try:
        children = tuple(tools_root.iterdir()) if tools_root.exists() else ()
    except OSError:
        return _unsafe(suite_root, tools_root, own_environment, "unreadable_tool_inventory")
    own = own_environment.resolve(strict=False)
    for child in children:
        if child.resolve(strict=False) == own or child.name in _UV_TOOL_CONTROL_FILES | {".nobackup"}:
            continue
        if not child.is_dir() or child.is_symlink():
            return _unsafe(suite_root, tools_root, own_environment, "unknown_tool_environment")
        ownership = _environment_owns_suite(child)
        if ownership is None:
            return _unsafe(suite_root, tools_root, own_environment, "uncertain_tool_inventory")
        if ownership:
            return _unsafe(suite_root, tools_root, own_environment, "other_suite_app_installed")
    actions = tuple(
        CleanupAction("delete_file", str(suite_root / name))
        for name in _KNOWN_FILES
        if (suite_root / name).is_file() and not (suite_root / name).is_symlink()
    )
    return CleanupPlan(
        str(suite_root),
        str(tools_root),
        str(own_environment),
        True,
        "no_other_suite_apps",
        (*actions, CleanupAction("remove_empty_dir", str(suite_root))),
    )


def execute_cleanup_plan(plan: CleanupPlan) -> CleanupPlan:
    """Recheck ownership after uv removes this tool, then apply a fresh plan."""
    own = Path(plan.own_environment)
    try:
        _ = own.lstat()
    except FileNotFoundError:
        own_present = False
    else:
        own_present = True
    if own_present:
        fresh = _unsafe(Path(plan.suite_root), Path(plan.tools_root), own, "own_environment_still_present")
    else:
        fresh = plan_suite_cleanup(
            suite_root=Path(plan.suite_root), tools_root=Path(plan.tools_root), own_environment=own
        )
    fresh = replace(
        fresh,
        finalize_script=plan.finalize_script,
        uninstall_marker=plan.uninstall_marker,
        operation_token=plan.operation_token,
    )
    if not fresh.safe_to_execute:
        return fresh
    for action in fresh.actions:
        target = Path(action.path)
        if action.kind == "delete_file" and target.is_file() and not target.is_symlink():
            target.unlink()
        elif action.kind == "remove_empty_dir":
            with contextlib.suppress(OSError):
                target.rmdir()
    return fresh


def _read_plan(path: Path) -> CleanupPlan:
    try:
        encoded = path.read_text(encoding="ascii").splitlines()
        if len(encoded) != 7:
            raise ValueError
        (
            suite_root,
            tools_root,
            own_environment,
            reason,
            finalize_script,
            uninstall_marker,
            operation_token,
        ) = tuple(
            "" if value == "-" else base64.b64decode(value, validate=True).decode("utf-8")
            for value in encoded
        )
        return CleanupPlan(
            suite_root,
            tools_root,
            own_environment,
            False,
            reason,
            (),
            finalize_script,
            uninstall_marker,
            operation_token,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise UninstallPreparationError(f"Cannot read cleanup plan: {path}") from exc


def _stop_verified_instance(state_root: Path) -> None:
    from filelock import Timeout

    from pdomain_ocr_simple_gui.instance import InstanceStore, request_instance

    store = InstanceStore(state_root)
    try:
        _ = store.lifetime_lock.acquire(timeout=0)
    except Timeout:
        try:
            record = store.read()
        except (OSError, ValueError) as exc:
            raise UninstallPreparationError("Active desktop runtime record is unreadable") from exc
        if record is None:
            raise UninstallPreparationError(
                "Active desktop runtime has no readable identity record"
            ) from None
        try:
            status = request_instance(record, "status")
        except (OSError, ValueError) as exc:
            raise UninstallPreparationError(
                "Active desktop runtime did not verify its native capability"
            ) from exc
        if not status.accepted:
            raise UninstallPreparationError("Active desktop runtime rejected the uninstall request") from None
        if status.active_operations:
            raise UninstallPreparationError(
                "OCR or another operation is active; finish it before uninstalling"
            ) from None
        if not request_instance(record, "quit", confirm_other_tabs=True).accepted:
            raise UninstallPreparationError("Active desktop runtime refused to quit") from None
    else:
        store.lifetime_lock.release()
        return
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            _ = store.lifetime_lock.acquire(timeout=0)
        except Timeout:
            time.sleep(0.1)
        else:
            store.lifetime_lock.release()
            return
    raise UninstallPreparationError("Desktop runtime did not stop within 30 seconds; no process was killed")


def _is_inside(path: Path, directory: Path) -> bool:
    return path.absolute().is_relative_to(directory.absolute())


def _base_python() -> Path:
    base_python = Path(getattr(sys, "_base_executable", sys.executable))
    if not base_python.is_file() or _is_inside(base_python, Path(sys.prefix)):
        raise UninstallPreparationError("Installed tool has no usable base Python for cleanup finalization")
    return base_python


def _marker_token(marker: Path) -> str:
    try:
        content = marker.read_text(encoding="utf-8")
    except OSError as exc:
        raise UninstallPreparationError("Existing uninstall marker cannot be read") from exc
    matched = re.fullmatch(
        r'\{"app_id": "pdomain-ocr-simple-gui", "operation_token": "([a-f0-9]{32})", "schema_version": 1\}',
        content,
    )
    if matched is None:
        raise UninstallPreparationError("Existing uninstall marker is malformed; repair is required")
    return matched.group(1)


def _prepared_result(
    plan: CleanupPlan, base_python: Path, locations: _Locations, plan_path: Path
) -> dict[str, object]:
    retained = [
        str(locations.config_root),
        str(locations.data_root),
        str(locations.state_root),
        str(locations.cache_root),
        str(locations.projects_root),
        str(locations.uploads_root),
        str(locations.outputs_root),
        str(locations.jobs_root),
    ]
    return {
        "prepared": True,
        "retained_paths": retained,
        "effective_env_overrides": dict(locations.overrides),
        "suite_cleanup": plan.to_json(),
        "base_python": str(base_python),
        "finalize_script": plan.finalize_script,
        "plan_path": str(plan_path),
        "uninstall_marker": plan.uninstall_marker,
        "operation_token": plan.operation_token,
    }


def _resume_preparation(
    state_root: Path, marker: Path, base_python: Path, locations: _Locations
) -> dict[str, object]:
    token = _marker_token(marker)
    plans = tuple(state_root.glob("uninstall-plan-*.json"))
    matching = tuple(
        (path, plan)
        for path in plans
        if (plan := _read_plan(path)).operation_token == token
        and plan.uninstall_marker == str(marker)
        and plan.own_environment == str(Path(sys.prefix))
        and Path(plan.finalize_script).is_file()
    )
    if len(matching) != 1:
        raise UninstallPreparationError("Existing uninstall preparation is incomplete; repair is required")
    plan_path, plan = matching[0]
    return _prepared_result(plan, base_python, locations, plan_path)


def _write_uninstall_marker(state_root: Path) -> tuple[Path, str]:
    marker = state_root / "uninstall-in-progress.json"
    if marker.exists():
        raise UninstallPreparationError("A previous uninstall is still in progress; retry or repair it first")
    token = uuid4().hex
    content = json.dumps({"app_id": APP_ID, "operation_token": token, "schema_version": 1}, sort_keys=True)
    descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        _ = stream.write(content)
    return marker, token


def _clear_matching_marker(plan: CleanupPlan) -> None:
    if not plan.uninstall_marker or not plan.operation_token:
        return
    marker = Path(plan.uninstall_marker)
    expected = json.dumps(
        {"app_id": APP_ID, "operation_token": plan.operation_token, "schema_version": 1}, sort_keys=True
    )
    if marker.is_file() and not marker.is_symlink() and marker.read_text(encoding="utf-8") == expected:
        marker.unlink()


def _guard_retained_location(path: Path) -> None:
    """Verify one retained path before any uninstall mutation."""
    from pdomain_ocr_simple_gui.locations import is_within_installation

    try:
        inside = is_within_installation(path)
    except (OSError, RuntimeError, ValueError) as exc:
        raise UninstallPreparationError(f"Cannot verify retained data location: {path}") from exc
    if inside:
        raise UninstallPreparationError(
            f"Data or model caches inside the installed app must be moved first: {path}"
        )


def _guard_project_outputs(projects_root: Path) -> None:
    """Read only direct owned project records when checking retained outputs."""
    from pydantic import TypeAdapter, ValidationError

    from pdomain_ocr_simple_gui.models import ProjectSpec, ProjectStatus

    try:
        children = tuple(projects_root.iterdir())
    except FileNotFoundError:
        return
    except OSError as exc:
        raise UninstallPreparationError(f"Cannot inspect project metadata: {projects_root}") from exc
    adapter = TypeAdapter(dict[str, object])
    for child in children:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", child.name) or child.is_symlink() or not child.is_dir():
            continue
        try:
            canonical_id = str(UUID(child.name)) == child.name
        except ValueError:
            canonical_id = False
        metadata = child / "project.json"
        try:
            _ = metadata.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UninstallPreparationError(f"Cannot read project metadata: {metadata}") from exc
        if metadata.is_symlink() or not metadata.is_file():
            if canonical_id:
                raise UninstallPreparationError(f"Cannot trust project metadata: {metadata}")
            continue
        try:
            text = metadata.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise UninstallPreparationError(f"Cannot read project metadata: {metadata}") from exc
        try:
            payload = adapter.validate_json(text)
            spec_payload = adapter.validate_python(payload.get("spec"))
            status_payload = adapter.validate_python(payload.get("status"))
        except ValidationError as exc:
            if canonical_id:
                raise UninstallPreparationError(f"Invalid project metadata: {metadata}") from exc
            continue
        if any(record.get("project_id") != child.name for record in (spec_payload, status_payload)):
            if canonical_id:
                raise UninstallPreparationError(f"Mismatched project metadata: {metadata}")
            continue
        try:
            spec = ProjectSpec.model_validate(spec_payload)
            status = ProjectStatus.model_validate(status_payload)
        except ValidationError as exc:
            raise UninstallPreparationError(f"Invalid project metadata: {metadata}") from exc
        for output in (spec.output_dir, status.output_dir):
            if output:
                _guard_retained_location(Path(output).expanduser())


def _guard_retained_locations(locations: _Locations) -> None:
    """Refuse package removal when it would erase retained user files."""
    from pydantic import TypeAdapter, ValidationError

    from pdomain_ocr_simple_gui.cache_configuration import effective_model_paths

    for path in (
        locations.config_root,
        locations.data_root,
        locations.state_root,
        locations.cache_root,
        locations.projects_root,
        locations.uploads_root,
        locations.outputs_root,
        locations.jobs_root,
    ):
        _guard_retained_location(path)
    _guard_project_outputs(locations.projects_root)
    for value in effective_model_paths().values():
        _guard_retained_location(Path(value).expanduser())
    for variable in ("DOCTR_CACHE_DIR", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "TORCH_HOME"):
        if value := os.environ.get(variable):
            _guard_retained_location(Path(value).expanduser())

    preferences = locations.config_root / "preferences.json"
    try:
        text = preferences.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeError) as exc:
        raise UninstallPreparationError(
            f"Cannot read retained model cache preferences: {preferences}"
        ) from exc
    adapter = TypeAdapter(dict[str, object])
    try:
        payload = adapter.validate_json(text)
        app = adapter.validate_python(payload.get("app"))
    except ValidationError as exc:
        raise UninstallPreparationError(
            f"Cannot read retained model cache preferences: {preferences}"
        ) from exc
    saved = app.get("model_cache_location", "")
    if not isinstance(saved, str):
        raise UninstallPreparationError(f"Invalid model cache preference in: {preferences}")
    if saved:
        root = Path(saved).expanduser()
        for path in (root, root / "doctr", root / "huggingface/hub", root / "torch/hub"):
            _guard_retained_location(path)


def prepare_uninstall(tools_root: Path) -> dict[str, object]:
    """Stop, unregister, and stage a stdlib-only finalizer before uv removal."""
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    import platformdirs
    from pdomain_ops.suite.paths import installed_toml_path
    from pdomain_ops.suite.registry import LocalTomlSuiteRegistry

    from pdomain_ocr_simple_gui.instance import InstanceStore
    from pdomain_ocr_simple_gui.locations import LocationConfigError, get_locations

    try:
        locations = get_locations()
    except (LocationConfigError, ValueError) as exc:
        raise UninstallPreparationError(f"Cannot resolve configured app data locations: {exc}") from exc
    _guard_retained_locations(locations)
    suite_override = os.environ.get("PD_SUITE_DATA_DIR")
    configured_suite_root = (
        Path(suite_override)
        if suite_override
        else Path(platformdirs.user_data_dir("pdomain-suite", appauthor=False))
    )
    # The dependency's canonical getter creates its directory. Check its
    # configured destination before invoking it, then verify the returned path.
    _guard_retained_location(configured_suite_root)
    registry_path = installed_toml_path()
    _guard_retained_location(registry_path.parent)
    base_python = _base_python()
    store = InstanceStore(locations.state_root)
    with store.startup_lock.acquire(timeout=30):
        _stop_verified_instance(locations.state_root)
        existing_marker = locations.state_root / "uninstall-in-progress.json"
        if existing_marker.exists():
            return _resume_preparation(locations.state_root, existing_marker, base_python, locations)
        marker, operation_token = _write_uninstall_marker(locations.state_root)
    script: Path | None = None
    plan_path: Path | None = None
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            LocalTomlSuiteRegistry(root=registry_path).unregister(APP_ID)
        plan = plan_suite_cleanup(
            suite_root=registry_path.parent,
            tools_root=tools_root,
            own_environment=Path(sys.prefix),
        )
        token = uuid4().hex
        script = locations.state_root / f"uninstall-finalize-{token}.py"
        plan_path = locations.state_root / f"uninstall-plan-{token}.json"
        _ = shutil.copyfile(Path(__file__), script)
        staged = replace(
            plan,
            finalize_script=str(script),
            uninstall_marker=str(marker),
            operation_token=operation_token,
        )
        plan_content = "\n".join(
            base64.b64encode(value.encode("utf-8")).decode("ascii") or "-"
            for value in (
                staged.suite_root,
                staged.tools_root,
                staged.own_environment,
                staged.reason,
                staged.finalize_script,
                staged.uninstall_marker,
                staged.operation_token,
            )
        )
        _ = plan_path.write_text(plan_content, encoding="ascii")
        return _prepared_result(staged, base_python, locations, plan_path)
    except Exception:
        if script is not None:
            script.unlink(missing_ok=True)
        if plan_path is not None:
            plan_path.unlink(missing_ok=True)
        _clear_matching_marker(
            CleanupPlan(
                "", "", "", False, "", (), uninstall_marker=str(marker), operation_token=operation_token
            )
        )
        raise


def main(argv: Sequence[str] | None = None) -> int:
    """Run preparation in the tool environment or finalization outside it."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_output = "--json" in arguments
    try:
        if "--prepare" in arguments:
            if "--tool-dir" not in arguments:
                raise UninstallPreparationError(
                    "--prepare requires the exact uv tool directory as --tool-dir"
                )
            index = arguments.index("--tool-dir")
            if index + 1 >= len(arguments):
                raise UninstallPreparationError("--tool-dir needs a path")
            result = prepare_uninstall(Path(arguments[index + 1]))
        else:
            if "--execute-plan" not in arguments:
                raise UninstallPreparationError("A cleanup plan is required")
            index = arguments.index("--execute-plan")
            if index + 1 >= len(arguments):
                raise UninstallPreparationError("--execute-plan needs a path")
            plan_path = Path(arguments[index + 1])
            plan = _read_plan(plan_path)
            outcome = execute_cleanup_plan(plan)
            if outcome.reason == "own_environment_still_present":
                raise UninstallPreparationError(
                    "App environment still exists. Retry uninstall; recovery files were kept."
                )
            _clear_matching_marker(outcome)
            result = {"prepared": False, "suite_cleanup": outcome.to_json()}
            if plan.finalize_script and Path(plan.finalize_script).resolve() == Path(__file__).resolve():
                plan_path.unlink(missing_ok=True)
                Path(__file__).unlink(missing_ok=True)
    except (OSError, UninstallPreparationError) as exc:
        _ = sys.stderr.write(f"Uninstall preparation failed: {exc}\n")
        return 1
    if json_output:
        _ = sys.stdout.write(f"{json.dumps(result)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
