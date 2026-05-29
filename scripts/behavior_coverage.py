"""Behavior coverage audit: cross-check declared behavior IDs vs cited IDs.

Source of truth = docs/specs/behavior/*.md. Tests cite IDs via a
``Covers: B-...`` docstring line or a ``@behavior("B-...")`` marker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# TC003 suppressed: Path is used at runtime by main() (Path(__file__) and
# directory I/O), not only in annotations.
from pathlib import Path  # noqa: TC003

ID_RE = re.compile(r"\b([BF]-[A-Z0-9]+-\d+)\b")
RECORD_HEADING_RE = re.compile(r"^###\s+([BF]-[A-Z0-9]+-\d+)\b", re.MULTILINE)


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
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "Covers:" in line or "@behavior" in line:
                cited.update(ID_RE.findall(line))
    return cited
