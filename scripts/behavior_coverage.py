"""Behavior coverage audit: cross-check declared behavior IDs vs cited IDs.

Source of truth = docs/specs/behavior/*.md. Tests cite IDs via a
``Covers: B-...`` docstring line or a ``@behavior("B-...")`` marker.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ID_RE = re.compile(r"\b([BF]-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+)\b")
RECORD_HEADING_RE = re.compile(r"^###\s+([BF]-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+)\b", re.MULTILINE)

# This scanner's own unit-test file contains example IDs inside string
# fixtures (not real citations). Skip it so it never pollutes the gate.
_SELF_TEST = "test_behavior_coverage.py"


@dataclass(frozen=True)
class Record:
    id: str
    regression: bool


def scan_declared(docs_dir: Path) -> dict[str, Record]:
    """Find every record/flow declared as an H3 heading, with its regression flag."""
    declared: dict[str, Record] = {}
    for md in sorted(docs_dir.glob("*.md")):
        if md.name in {"coverage.md", "README.md"}:
            continue
        text = md.read_text(encoding="utf-8")
        # Split into blocks starting at each H3 record heading.
        matches = list(RECORD_HEADING_RE.finditer(text))
        for i, m in enumerate(matches):
            rec_id = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block = text[start:end]
            regression = bool(re.search(r"\*\*Regression:\*\*\s*yes", block, re.IGNORECASE))
            declared[rec_id] = Record(id=rec_id, regression=regression)
    return declared


def scan_cited(tests_dir: Path) -> set[str]:
    """Find every behavior ID cited in test files (docstring or marker)."""
    cited: set[str] = set()
    for py in tests_dir.rglob("*.py"):
        if py.name == _SELF_TEST:
            continue
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "Covers:" in line or "@behavior" in line:
                cited.update(ID_RE.findall(line))
    return cited


def _is_test_path(path: Path) -> bool:
    return (
        path.name == _SELF_TEST
        or path.name.startswith("test_")
        or ".test." in path.name
        or "__tests__" in path.parts
        or "tests" in path.parts
    )


def _existing_roots(root: Path, candidates: tuple[Path, ...]) -> tuple[Path, ...]:
    existing = tuple(path for path in candidates if path.exists())
    return existing or (root,)


def _machine_source_roots(root: Path) -> tuple[Path, ...]:
    return _existing_roots(
        root,
        (
            root / "frontend" / "src" / "statecharts",
            root / "src",
        ),
    )


def _machine_test_roots(root: Path) -> tuple[Path, ...]:
    return _existing_roots(
        root,
        (
            root / "frontend" / "src" / "statecharts" / "__tests__",
            root / "tests",
        ),
    )


def scan_machine_modeled(root: Path) -> set[str]:
    """Find behavior IDs exposed by frontend/backend machine metadata."""
    modeled: set[str] = set()
    for scan_root in _machine_source_roots(root):
        for path in sorted(scan_root.rglob("*")):
            if path.suffix not in {".py", ".ts"} or _is_test_path(path):
                continue
            text = path.read_text(encoding="utf-8")
            if "BEHAVIOR" in text or "behavior_ids" in text:
                modeled.update(ID_RE.findall(text))
    return modeled


def scan_machine_tested(root: Path) -> set[str]:
    """Find every behavior ID cited by runtime machine tests."""
    machine_tested: set[str] = set()
    for scan_root in _machine_test_roots(root):
        for path in sorted(scan_root.rglob("*")):
            if path.suffix not in {".py", ".ts", ".tsx"} or not _is_test_path(path):
                continue
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "Machine-Covers:" in line:
                    machine_tested.update(ID_RE.findall(line))
    return machine_tested


@dataclass(frozen=True)
class Report:
    declared: dict[str, Record]
    cited: set[str]
    modeled: set[str]
    machine_tested: set[str]
    orphans: set[str]
    unlinked: set[str]
    uncovered_regressions: set[str]

    @property
    def ok(self) -> bool:
        return not self.unlinked and not self.uncovered_regressions


def build_report(
    declared: dict[str, Record],
    cited: set[str],
    modeled: set[str] | None = None,
    machine_tested: set[str] | None = None,
) -> Report:
    declared_ids = set(declared)
    modeled = set() if modeled is None else modeled
    machine_tested = set() if machine_tested is None else machine_tested
    tested = cited | machine_tested
    orphans = declared_ids - tested
    unlinked = (tested | modeled) - declared_ids
    uncovered_regressions = {rid for rid in orphans if declared[rid].regression}
    return Report(
        declared=declared,
        cited=cited,
        modeled=modeled,
        machine_tested=machine_tested,
        orphans=orphans,
        unlinked=unlinked,
        uncovered_regressions=uncovered_regressions,
    )


def render_markdown(report: Report) -> str:
    lines = [
        "# Behavior coverage (generated — do not edit)",
        "",
        "Run `make behavior-coverage` to regenerate.",
        "",
        "| ID | Regression | Documented | Modeled | Tested |",
        "|----|------------|------------|---------|--------|",
    ]
    tested = report.cited | report.machine_tested
    for rid in sorted(report.declared):
        rec = report.declared[rid]
        reg = "yes" if rec.regression else "no"
        modeled = "yes" if rid in report.modeled else "no"
        tested_status = "yes" if rid in tested else "no"
        lines.append(f"| {rid} | {reg} | yes | {modeled} | {tested_status} |")
    if report.unlinked:
        lines += ["", "## Unlinked citations (FAIL — typo/stale)", ""]
        lines += [f"- {rid}" for rid in sorted(report.unlinked)]
    if report.uncovered_regressions:
        lines += ["", "## Uncovered regressions (FAIL)", ""]
        lines += [f"- {rid}" for rid in sorted(report.uncovered_regressions)]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    docs_dir = root / "docs" / "specs" / "behavior"
    tests_dir = root / "tests"
    declared = scan_declared(docs_dir)
    cited = scan_cited(tests_dir)
    modeled = scan_machine_modeled(root)
    machine_tested = scan_machine_tested(root)
    report = build_report(declared, cited, modeled, machine_tested)
    (docs_dir / "coverage.md").write_text(render_markdown(report), encoding="utf-8")
    if not report.ok:
        print("BEHAVIOR COVERAGE GATE FAILED", file=sys.stderr)
        if report.unlinked:
            print(f"  unlinked citations: {sorted(report.unlinked)}", file=sys.stderr)
        if report.uncovered_regressions:
            print(
                f"  uncovered regressions: {sorted(report.uncovered_regressions)}",
                file=sys.stderr,
            )
        return 1
    tested = cited | machine_tested
    print(f"behavior coverage OK: {len(declared)} records, {len(modeled)} modeled, {len(tested)} tested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
