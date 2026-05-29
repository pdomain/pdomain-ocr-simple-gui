from pathlib import Path

from scripts.behavior_coverage import (
    Record,
    build_report,
    render_markdown,
    scan_cited,
    scan_declared,
)


def test_scan_declared_finds_ids_and_regression_flag(tmp_path: Path) -> None:
    doc = tmp_path / "screen-home.md"
    doc.write_text(
        "# Screen behavior spec — Home\n\n"
        "### B-HOME-001 — Upload a ZIP\n\n"
        "- **Regression:** no\n\n"
        "### B-HOME-002 — Reject bad file\n\n"
        "- **Regression:** yes (#fixed-2026-04)\n",
        encoding="utf-8",
    )
    declared = scan_declared(tmp_path)
    assert declared["B-HOME-001"].regression is False
    assert declared["B-HOME-002"].regression is True


def test_scan_cited_finds_docstring_and_marker(tmp_path: Path) -> None:
    test_file = tmp_path / "test_x.py"
    test_file.write_text(
        'def test_a():\n    """Covers: B-HOME-001"""\n    pass\n\n'
        '@behavior("B-HOME-002")\n'
        "def test_b():\n    pass\n",
        encoding="utf-8",
    )
    cited = scan_cited(tmp_path)
    assert cited == {"B-HOME-001", "B-HOME-002"}


def test_scan_cited_skips_own_test_file(tmp_path: Path) -> None:
    # IDs inside the scanner's own unit-test fixtures must not count as
    # real citations, or the gate would flag them as unlinked.
    self_test = tmp_path / "test_behavior_coverage.py"
    self_test.write_text(
        'def test_x():\n    """Covers: B-HOME-001"""\n    pass\n',
        encoding="utf-8",
    )
    assert scan_cited(tmp_path) == set()


def test_build_report_flags_orphan_regression_and_unlinked() -> None:
    declared = {
        "B-HOME-001": Record("B-HOME-001", regression=False),  # specified, no test
        "B-HOME-002": Record("B-HOME-002", regression=True),  # regression, no test -> FAIL
        "B-HOME-003": Record("B-HOME-003", regression=True),  # regression, cited -> ok
    }
    cited = {"B-HOME-003", "B-RESULTS-999"}  # last one is unlinked
    report = build_report(declared, cited)
    assert report.orphans == {"B-HOME-001", "B-HOME-002"}
    assert report.unlinked == {"B-RESULTS-999"}
    assert report.uncovered_regressions == {"B-HOME-002"}
    assert report.ok is False  # gate fails


def test_build_report_ok_when_clean() -> None:
    declared = {"B-HOME-001": Record("B-HOME-001", regression=True)}
    report = build_report(declared, {"B-HOME-001"})
    assert report.ok is True
    assert report.uncovered_regressions == set()
    assert report.unlinked == set()


def test_render_markdown_lists_status() -> None:
    declared = {
        "B-HOME-001": Record("B-HOME-001", regression=False),
        "B-HOME-003": Record("B-HOME-003", regression=True),
    }
    report = build_report(declared, {"B-HOME-003"})
    md = render_markdown(report)
    assert "B-HOME-001" in md
    assert "specified" in md  # not cited
    assert "test-written" in md  # cited
    assert "do not edit" in md.lower()
