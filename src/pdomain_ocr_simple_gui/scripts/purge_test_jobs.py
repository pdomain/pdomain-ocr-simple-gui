"""Purge ephemeral e2e test-job artifacts from the projects, output, and jobs-meta roots.

Removes any directory under each root whose name matches a known e2e
test-job prefix, and drops matching ids from the prefs ``recent_projects`` list.

Usage (manual)::

    python -m pdomain_ocr_simple_gui.scripts.purge_test_jobs

Roots are resolved from env vars (same as the backend) or installed defaults:

- ``PD_OCR_SIMPLE_GUI_PROJECTS_ROOT``
- ``PD_OCR_SIMPLE_GUI_OUTPUT_ROOT``
- ``PD_OCR_SIMPLE_GUI_JOBS_META_ROOT``

Pass ``--dry-run`` to preview without deleting.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

_APP_ID = "pdomain-ocr-simple-gui"

_DEFAULT_PROJECTS_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-suite" / "simple-gui" / "projects"
_DEFAULT_OUTPUT_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-ocr-simple-gui" / "outputs"
_DEFAULT_JOBS_META_ROOT: Path = Path.home() / ".local" / "share" / "pdomain-ocr-simple-gui" / "jobs"


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


def _purge_root(root: Path, *, dry_run: bool) -> set[str]:
    """Remove test-job dirs from a single root; return set of removed ids."""
    from pdomain_ocr_simple_gui._testjobs import is_test_job

    if not root.exists():
        logger.debug("root does not exist; nothing to purge: %s", root)
        return set()

    removed: set[str] = set()
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if not is_test_job(entry.name):
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

    removed_ids: set[str] = set()
    removed_ids |= _purge_root(p_root, dry_run=dry_run)
    removed_ids |= _purge_root(o_root, dry_run=dry_run)
    removed_ids |= _purge_root(j_root, dry_run=dry_run)

    removed = sorted(removed_ids)
    if removed:
        _drop_from_prefs(removed, prefs_adapter, dry_run=dry_run)

    return removed


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
                from pdomain_ops.suite.prefs import LocalFilePrefs  # pyright: ignore[reportMissingTypeStubs]
            except ImportError:
                logger.warning("pdomain_ops not available; skipping prefs cleanup")
                return
            adapter = LocalFilePrefs()

        remove_set = set(ids_to_remove)
        raw_prefs = adapter.read()

        # Narrow to UIPrefs to get typed .apps access; fall back to safe empty
        # dict on any other type so the prefs step is skipped harmlessly.
        try:
            from pdomain_ops.suite.prefs import UIPrefs  # pyright: ignore[reportMissingTypeStubs]
        except ImportError:
            logger.warning("pdomain_ops not available; skipping prefs cleanup")
            return
        if not isinstance(raw_prefs, UIPrefs):
            logger.debug("Prefs object is not UIPrefs (%r); skipping cleanup", type(raw_prefs))
            return
        apps_dict: dict[str, dict[str, object]] = raw_prefs.apps  # type: ignore[assignment]

        app_data = apps_dict.get(_APP_ID)
        if not app_data or not isinstance(app_data, dict):
            return
        raw_recent = app_data.get("recent_projects")
        if not isinstance(raw_recent, list):
            return
        recent: list[dict[str, object]] = [p for p in raw_recent if isinstance(p, dict)]
        filtered = [p for p in recent if p.get("project_id") not in remove_set]
        if len(filtered) == len(recent):
            return  # nothing changed
        if dry_run:
            logger.info("[dry-run] would drop %d entries from recent_projects", len(recent) - len(filtered))
            return
        app_data_updated: dict[str, object] = dict(app_data)  # type: ignore[arg-type]
        app_data_updated["recent_projects"] = filtered
        adapter.write_app(_APP_ID, app_data_updated)
        logger.info("Dropped %d test-job entries from recent_projects", len(recent) - len(filtered))
    except Exception:  # prefs cleanup is best-effort
        logger.exception("Failed to clean test-job entries from prefs recent_projects")


@dataclass
class _CliArgs:
    dry_run: bool = False


def _parse_args() -> _CliArgs:
    """Parse command-line arguments for the purge script."""
    parser = argparse.ArgumentParser(description="Purge e2e test-job artifacts")
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without deleting",
    )
    import sys

    return parser.parse_args(sys.argv[1:], namespace=_CliArgs())  # type: ignore[return-value]


def _main() -> None:
    """Entry point for ``python -m pdomain_ocr_simple_gui.scripts.purge_test_jobs``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()

    removed = purge(dry_run=args.dry_run)
    if removed:
        for pid in removed:
            print(f"  {'[dry-run] ' if args.dry_run else ''}removed: {pid}")  # noqa: T201
        print(f"\n{'Would remove' if args.dry_run else 'Removed'} {len(removed)} test job(s).")  # noqa: T201
    else:
        print("No test jobs found.")  # noqa: T201


if __name__ == "__main__":
    _main()
