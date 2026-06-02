from pathlib import Path

from scripts.behavior_coverage import (
    Record,
    build_report,
    render_markdown,
    scan_cited,
    scan_declared,
    scan_machine_modeled,
    scan_machine_tested,
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
    report = build_report(declared, {"B-HOME-003"}, modeled={"B-HOME-001"})
    md = render_markdown(report)
    assert "| ID | Regression | Documented | Modeled | Tested |" in md
    assert "| B-HOME-001 | no | yes | yes | no |" in md
    assert "| B-HOME-003 | yes | yes | no | yes |" in md
    assert "do not edit" in md.lower()


def test_build_report_combines_machine_tested_ids_for_gate_and_rendering() -> None:
    declared = {
        "B-HOME-001": Record("B-HOME-001", regression=False),
        "B-HOME-002": Record("B-HOME-002", regression=True),
        "B-HOME-003": Record("B-HOME-003", regression=True),
    }
    report = build_report(
        declared,
        cited={"B-HOME-001"},
        modeled={"B-HOME-002", "B-HOME-003"},
        machine_tested={"B-HOME-002", "B-HOME-999"},
    )

    assert report.modeled == {"B-HOME-002", "B-HOME-003"}
    assert report.machine_tested == {"B-HOME-002", "B-HOME-999"}
    assert report.unlinked == {"B-HOME-999"}
    assert report.uncovered_regressions == {"B-HOME-003"}

    md = render_markdown(report)
    assert "| ID | Regression | Documented | Modeled | Tested |" in md
    assert "| B-HOME-001 | no | yes | no | yes |" in md
    assert "| B-HOME-002 | yes | yes | yes | yes |" in md
    assert "| B-HOME-003 | yes | yes | yes | no |" in md


def test_scan_declared_finds_multi_segment_flow_id(tmp_path: Path) -> None:
    """Multi-segment IDs like F-UPLOAD-OCR-DOWNLOAD-01 are declared and scanned.

    The regex must allow optional inner segments so that IDs with more than
    one token between the prefix letter and the numeric suffix are matched.
    Single-segment IDs (B-HOME-001, F-RERUN-01) must also still match.
    """
    doc = tmp_path / "flows.md"
    doc.write_text(
        "# Cross-unit flows\n\n"
        "### F-UPLOAD-OCR-DOWNLOAD-01 — Flagship happy path\n\n"
        "- **Regression:** no\n\n"
        "### F-RERUN-01 — Single-page rerun\n\n"
        "- **Regression:** yes\n",
        encoding="utf-8",
    )
    declared = scan_declared(tmp_path)
    assert "F-UPLOAD-OCR-DOWNLOAD-01" in declared, f"Multi-segment ID not found in declared={set(declared)!r}"
    assert "F-RERUN-01" in declared, f"Single-segment ID not found in declared={set(declared)!r}"
    assert declared["F-UPLOAD-OCR-DOWNLOAD-01"].regression is False
    assert declared["F-RERUN-01"].regression is True


def test_scan_cited_finds_multi_segment_flow_id(tmp_path: Path) -> None:
    """scan_cited must match multi-segment IDs in Covers: lines."""
    test_file = tmp_path / "test_flows.py"
    test_file.write_text(
        'def test_flagship():\n    """Covers: F-UPLOAD-OCR-DOWNLOAD-01"""\n    pass\n\n'
        'def test_rerun():\n    """Covers: F-RERUN-01"""\n    pass\n',
        encoding="utf-8",
    )
    cited = scan_cited(tmp_path)
    assert "F-UPLOAD-OCR-DOWNLOAD-01" in cited, f"Multi-segment ID not found in cited={cited!r}"
    assert "F-RERUN-01" in cited, f"Single-segment ID not found in cited={cited!r}"


def test_scan_machine_modeled_finds_ids_in_frontend_and_python_metadata(tmp_path: Path) -> None:
    ts_machine_metadata = tmp_path / "frontend" / "src" / "statecharts" / "jobCreationBehavior.ts"
    ts_machine_metadata.parent.mkdir(parents=True)
    ts_machine_metadata.write_text(
        "export const JOB_CREATION_BEHAVIOR = {\n"
        '  uploadViaDropOrPicker: "B-HOME-002",\n'
        '  submitJob: "B-HOME-011",\n'
        "} as const;\n",
        encoding="utf-8",
    )
    py_machine_metadata = tmp_path / "src" / "statecharts" / "job_lifecycle.py"
    py_machine_metadata.parent.mkdir(parents=True)
    py_machine_metadata.write_text(
        'behavior_ids = {\n    ("new", "queue", "queued"): ("B-HOME-014",),\n}\n',
        encoding="utf-8",
    )
    test_fixture = tmp_path / "tests" / "test_machine.py"
    test_fixture.parent.mkdir()
    test_fixture.write_text(
        'JOB_TEST_BEHAVIOR = {"B-HOME-999"}\n',
        encoding="utf-8",
    )

    assert scan_machine_modeled(tmp_path) == {
        "B-HOME-002",
        "B-HOME-011",
        "B-HOME-014",
    }


def test_scan_machine_tested_finds_ids_in_machine_covers_lines(tmp_path: Path) -> None:
    ts_test = tmp_path / "frontend" / "src" / "statecharts" / "__tests__" / "jobCreationMachine.test.ts"
    ts_test.parent.mkdir(parents=True)
    ts_test.write_text(
        "// Machine-Covers: B-HOME-002 B-HOME-003\nit('covers source selection', () => {});\n",
        encoding="utf-8",
    )
    py_test = tmp_path / "tests" / "test_job_lifecycle_statechart.py"
    py_test.parent.mkdir()
    py_test.write_text(
        "def test_lifecycle_behavior_mapping_uses_documented_ids():\n"
        '    """Machine-Covers: B-HOME-011"""\n'
        "    pass\n",
        encoding="utf-8",
    )
    source_comment = tmp_path / "frontend" / "src" / "statecharts" / "jobCreationMachine.tsx"
    source_comment.parent.mkdir(parents=True, exist_ok=True)
    source_comment.write_text(
        "// Machine-Covers: B-HOME-014\n",
        encoding="utf-8",
    )

    assert scan_machine_tested(tmp_path) == {
        "B-HOME-002",
        "B-HOME-003",
        "B-HOME-011",
        "B-HOME-014",
    }
