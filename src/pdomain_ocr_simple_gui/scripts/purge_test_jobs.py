"""Purge ephemeral e2e test-job artifacts from the projects, output, and jobs-meta roots.

A project directory is identified as a test artifact by one of three signatures
(classified from the projects root, which is the only root carrying
``project.json``):

1. **pytest-tmp source** (PRIMARY, false-positive-proof): ``spec.source_path``
   is under a pytest tmp dir (``/tmp/pytest-*`` / ``pytest-of-*``).  A real user
   job's source is never there.  Catches the UUID-named leaked jobs.
2. **legacy prefix**: ``project_id`` starts with a known fixture prefix
   (e.g. ``e2etestjob-``).
3. **degenerate-empty**: empty name AND empty source AND zero pages.

Conservative guarantees:

- A job named ``ocr-job-*`` is never matched (canonical user job prefix).
- A job with any pages or any non-pytest-tmp source is never matched.

Leaked ids found in the projects root are also removed from the output and
jobs-meta mirror roots, and dropped from the prefs ``recent_projects`` list.

Usage (manual)::

    python -m pdomain_ocr_simple_gui.scripts.purge_test_jobs            # dry-run
    python -m pdomain_ocr_simple_gui.scripts.purge_test_jobs --apply    # delete

Roots are resolved from env vars (same as the backend) or installed defaults:

- ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT``
- ``PD_OCR_SIMPLE_GUI_OUTPUT_ROOT``
- ``PD_OCR_SIMPLE_GUI_JOBS_META_ROOT``

Default mode is a safe dry-run (deletes nothing); pass ``--apply`` to delete.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

logger = logging.getLogger(__name__)

_APP_ID = "pdomain-ocr-simple-gui"

_DEFAULT_PROJECTS_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"
_DEFAULT_OUTPUT_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-ocr-simple-gui" / "outputs"
_DEFAULT_JOBS_META_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-ocr-simple-gui" / "jobs"

# ---------------------------------------------------------------------------
# Signature-based detection
#
# The robust, false-positive-proof signal is "source_path under a pytest tmp
# dir" — a real user job's source is never there.  That predicate lives in
# ``_testjobs`` so the runtime filter and this purge agree exactly.  The legacy
# ``e2etestjob-`` id prefix is a secondary signal.  A degenerate artifact
# (empty name AND empty source AND zero pages) is a third, narrowly-scoped
# category that can never touch a job with real pages or a real source.
# ---------------------------------------------------------------------------

# Category labels for the purge summary.
CAT_PYTEST_SOURCE = "pytest-tmp-source"
CAT_LEGACY_PREFIX = "legacy-prefix"
CAT_DEGENERATE = "degenerate-empty"
CAT_KEEP = "keep"


@dataclass(frozen=True)
class _ProjectMeta:
    """Minimal project.json fields needed for classification."""

    name: str
    source_path: str
    page_count: int


def _read_project_meta(proj_dir: Path) -> _ProjectMeta | None:
    """Read (name, source_path, page_count) from project.json; None if unreadable.

    ``page_count`` is read from ``status.page_count`` (falling back to the
    length of ``status.pages``) so the degenerate-job check can require zero
    pages.
    """
    proj_file = proj_dir / "project.json"
    if not proj_file.exists():
        return None
    try:
        raw: object = cast("object", json.loads(proj_file.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001  # JSON decode / IO errors all treated as "unreadable"
        return None
    if not isinstance(raw, dict):
        return None
    typed_raw: dict[str, object] = cast("dict[str, object]", raw)
    spec_raw: object = typed_raw.get("spec", {})
    status_raw: object = typed_raw.get("status", {})
    spec: dict[str, object] = cast("dict[str, object]", spec_raw) if isinstance(spec_raw, dict) else {}
    status: dict[str, object] = cast("dict[str, object]", status_raw) if isinstance(status_raw, dict) else {}
    name = str(spec.get("name", ""))
    source_path = str(spec.get("source_path", ""))
    page_count_raw: object = status.get("page_count")
    if not isinstance(page_count_raw, int):
        pages_raw: object = status.get("pages")
        page_count: int = len(cast("list[object]", pages_raw)) if isinstance(pages_raw, list) else 0
    else:
        page_count = page_count_raw
    return _ProjectMeta(name=name, source_path=source_path, page_count=page_count)


def _is_degenerate_job(meta: _ProjectMeta) -> bool:
    """Return True for the empty-name / empty-source / zero-page test artifact.

    Narrowly scoped on purpose: a job with ANY pages or ANY non-empty source is
    never degenerate, so this rule can never delete real work.
    """
    return not meta.name and not meta.source_path and meta.page_count == 0


def classify_entry(entry: Path) -> str:
    """Classify a project directory into a purge category.

    Returns one of ``CAT_PYTEST_SOURCE``, ``CAT_LEGACY_PREFIX``,
    ``CAT_DEGENERATE`` (all purgeable) or ``CAT_KEEP`` (preserved).

    Detection order:
    1. Legacy id prefix (cheap, no IO).
    2. Read project.json (projects root only); classify by pytest-tmp source
       path or degenerate emptiness.  Dirs with no readable project.json (e.g.
       output / jobs-meta mirror dirs) fall through to ``CAT_KEEP`` here and are
       removed via the cross-root id propagation in :func:`purge`.
    """
    from pdomain_ocr_simple_gui._testjobs import is_test_job, is_test_source_path

    # Cheap path: legacy id prefix.
    if is_test_job(entry.name):
        return CAT_LEGACY_PREFIX

    meta = _read_project_meta(entry)
    if meta is None:
        return CAT_KEEP
    # Canonical user job prefix is never a test artifact.
    if meta.name.startswith("ocr-job-"):
        return CAT_KEEP
    if is_test_source_path(meta.source_path):
        return CAT_PYTEST_SOURCE
    if _is_degenerate_job(meta):
        return CAT_DEGENERATE
    return CAT_KEEP


def _default_projects_root() -> Path:
    """Return the projects root, honouring the env var the backend uses."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT")
    return Path(raw) if raw else _DEFAULT_PROJECTS_ROOT


def _default_output_root() -> Path:
    """Return the output root, honouring the env var the backend uses."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT")
    return Path(raw) if raw else _DEFAULT_OUTPUT_ROOT


def _default_jobs_meta_root() -> Path:
    """Return the jobs-meta root, honouring the env var the backend uses."""
    raw = os.environ.get("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT")
    return Path(raw) if raw else _DEFAULT_JOBS_META_ROOT


class _PrefsAdapterProtocol(Protocol):
    """Minimal duck-type surface used by the purge script."""

    def read(self) -> object:
        """Return the current prefs (UIPrefs or compatible)."""
        ...

    def write_app(self, app_id: str, payload: dict[str, object]) -> None:
        """Write per-app blob."""
        ...


def classify_projects_root(root: Path) -> dict[str, list[str]]:
    """Classify every directory in the projects *root* into purge categories.

    Returns a mapping of category label -> sorted list of project ids.  Only
    the projects root carries project.json, so this is the authoritative
    source of the leaked-id set used to also clean the output / jobs-meta
    mirror roots.
    """
    buckets: dict[str, list[str]] = {
        CAT_PYTEST_SOURCE: [],
        CAT_LEGACY_PREFIX: [],
        CAT_DEGENERATE: [],
        CAT_KEEP: [],
    }
    if not root.exists():
        return buckets
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        buckets[classify_entry(entry)].append(entry.name)
    return buckets


def _purge_dirs_by_id(root: Path, ids: set[str], *, dry_run: bool) -> set[str]:
    """Remove directories whose name is in *ids* from a single root.

    Also removes any directory whose name carries a legacy test-job prefix even
    if it is not in *ids* (e.g. prefix-named mirror dirs in output / jobs-meta
    roots that never had a project.json).
    """
    from pdomain_ocr_simple_gui._testjobs import is_test_job

    if not root.exists():
        logger.debug("root does not exist; nothing to purge: %s", root)
        return set()

    removed: set[str] = set()
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name not in ids and not is_test_job(entry.name):
            continue
        removed.add(entry.name)
        if dry_run:
            logger.info("[dry-run] would remove: %s", entry)
        else:
            logger.info("Removing test job dir: %s", entry)
            shutil.rmtree(entry)
    return removed


def purge(
    projects_root: Path | None = None,
    output_root: Path | None = None,
    jobs_meta_root: Path | None = None,
    prefs_adapter: _PrefsAdapterProtocol | None = None,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Remove all test-job dirs and clean prefs recent_projects.

    Args:
        projects_root: Override the projects root directory.  Defaults to
            the env-var-resolved default (``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT``).
        output_root: Override the output root directory.  Defaults to
            the env-var-resolved default (``PD_OCR_SIMPLE_GUI_OUTPUT_ROOT``).
        jobs_meta_root: Override the jobs-meta root directory.  Defaults to
            the env-var-resolved default (``PD_OCR_SIMPLE_GUI_JOBS_META_ROOT``).
        prefs_adapter: Optional ``PrefsAdapter``-compatible object for
            reading/writing recent_projects.  When ``None`` the function
            attempts to construct a ``LocalFilePrefs`` from the default
            suite data dir.  If construction fails the prefs step is
            skipped with a warning.
        dry_run: Log what would be removed but do not actually remove
            anything.  The returned list still contains the *would-be*
            removed ids.

    Returns:
        Deduplicated list of project_id strings that were (or would be) removed
        across all three roots.
    """
    p_root = projects_root if projects_root is not None else _default_projects_root()
    o_root = output_root if output_root is not None else _default_output_root()
    j_root = jobs_meta_root if jobs_meta_root is not None else _default_jobs_meta_root()

    # The projects root is authoritative: only it has project.json, so classify
    # there and propagate the leaked-id set to the mirror roots.
    buckets = classify_projects_root(p_root)
    leaked_ids: set[str] = set()
    for cat in (CAT_PYTEST_SOURCE, CAT_LEGACY_PREFIX, CAT_DEGENERATE):
        leaked_ids.update(buckets[cat])

    removed_ids: set[str] = set()
    removed_ids |= _purge_dirs_by_id(p_root, leaked_ids, dry_run=dry_run)
    removed_ids |= _purge_dirs_by_id(o_root, leaked_ids, dry_run=dry_run)
    removed_ids |= _purge_dirs_by_id(j_root, leaked_ids, dry_run=dry_run)

    removed = sorted(removed_ids)
    if removed:
        _drop_from_prefs(removed, prefs_adapter, dry_run=dry_run)

    return removed


def summarize(projects_root: Path | None = None) -> dict[str, list[str]]:
    """Return the per-category classification of the projects root (read-only).

    Categories are ``CAT_PYTEST_SOURCE``, ``CAT_LEGACY_PREFIX``,
    ``CAT_DEGENERATE`` (purgeable) and ``CAT_KEEP`` (preserved).  Touches no
    filesystem state beyond reading project.json files.
    """
    p_root = projects_root if projects_root is not None else _default_projects_root()
    return classify_projects_root(p_root)


def _drop_from_prefs(
    ids_to_remove: list[str],
    adapter: _PrefsAdapterProtocol | None,
    *,
    dry_run: bool,
) -> None:
    """Drop *ids_to_remove* from prefs recent_projects (best-effort)."""
    try:
        if adapter is None:
            # Attempt to build a default adapter; skip on import error
            try:
                from pdomain_ops.suite.prefs import LocalFilePrefs
            except ImportError:
                logger.warning("pdomain_ops not available; skipping prefs cleanup")
                return
            adapter = LocalFilePrefs()

        remove_set = set(ids_to_remove)
        raw_prefs = adapter.read()

        # Narrow to UIPrefs to get typed .apps access; fall back to safe empty
        # dict on any other type so the prefs step is skipped harmlessly.
        try:
            from pdomain_ops.suite.types import UIPrefs
        except ImportError:
            logger.warning("pdomain_ops not available; skipping prefs cleanup")
            return
        if not isinstance(raw_prefs, UIPrefs):
            logger.debug("Prefs object is not UIPrefs (%r); skipping cleanup", type(raw_prefs))
            return
        apps_dict: dict[str, dict[str, object]] = cast("dict[str, dict[str, object]]", raw_prefs.apps)

        app_data = apps_dict.get(_APP_ID)
        if not app_data:
            return
        raw_recent: object = app_data.get("recent_projects")
        if not isinstance(raw_recent, list):
            return
        recent_raw: list[object] = cast("list[object]", raw_recent)
        recent: list[dict[str, object]] = [
            cast("dict[str, object]", p) for p in recent_raw if isinstance(p, dict)
        ]
        filtered = [p for p in recent if p.get("project_id") not in remove_set]
        if len(filtered) == len(recent):
            return  # nothing changed
        if dry_run:
            logger.info("[dry-run] would drop %d entries from recent_projects", len(recent) - len(filtered))
            return
        app_data_updated: dict[str, object] = dict(app_data)
        app_data_updated["recent_projects"] = filtered
        adapter.write_app(_APP_ID, app_data_updated)
        logger.info("Dropped %d test-job entries from recent_projects", len(recent) - len(filtered))
    except Exception:  # prefs cleanup is best-effort
        logger.exception("Failed to clean test-job entries from prefs recent_projects")


@dataclass
class _CliArgs:
    dry_run: bool = True
    apply: bool = False


def _parse_args() -> _CliArgs:
    """Parse command-line arguments for the purge script."""
    parser = argparse.ArgumentParser(
        description="Purge e2e test-job artifacts (prefix + signature matching)",
        epilog=("Default mode is --dry-run (safe preview).  Pass --apply to actually delete."),
    )
    group = parser.add_mutually_exclusive_group()
    _ = group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview without deleting (default).",
    )
    _ = group.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually delete the identified test-job directories.",
    )
    import sys

    return parser.parse_args(sys.argv[1:], namespace=_CliArgs())  # type: ignore[return-value]


def _print_category(label: str, ids: list[str], *, sample: int = 5) -> None:
    """Print a one-line count + a small sample of ids for one category."""
    head = ", ".join(ids[:sample])
    more = f", … (+{len(ids) - sample} more)" if len(ids) > sample else ""
    suffix = f"  e.g. {head}{more}" if ids else ""
    print(f"  {label:<18} {len(ids):>4}{suffix}")  # noqa: T201


def _main() -> None:
    """Entry point for ``python -m pdomain_ocr_simple_gui.scripts.purge_test_jobs``."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = _parse_args()
    dry_run = not args.apply

    # Always classify first and print a per-category summary.
    buckets = summarize()
    would_delete = buckets[CAT_PYTEST_SOURCE] + buckets[CAT_LEGACY_PREFIX] + buckets[CAT_DEGENERATE]
    mode = "DRY-RUN (no deletions)" if dry_run else "APPLY (deleting)"
    print(f"== purge_test_jobs [{mode}] ==")  # noqa: T201
    print("Would delete:")  # noqa: T201
    _print_category(CAT_PYTEST_SOURCE, buckets[CAT_PYTEST_SOURCE])
    _print_category(CAT_LEGACY_PREFIX, buckets[CAT_LEGACY_PREFIX])
    _print_category(CAT_DEGENERATE, buckets[CAT_DEGENERATE])
    print("Would keep:")  # noqa: T201
    _print_category(CAT_KEEP, buckets[CAT_KEEP])
    print(f"\nTotal: delete {len(would_delete)}  |  keep {len(buckets[CAT_KEEP])}")  # noqa: T201

    removed = purge(dry_run=dry_run)
    action = "Would remove" if dry_run else "Removed"
    print(f"{action} {len(removed)} directory id(s) across all roots.")  # noqa: T201
    if dry_run:
        print("Pass --apply to actually delete.")  # noqa: T201


if __name__ == "__main__":
    _main()
