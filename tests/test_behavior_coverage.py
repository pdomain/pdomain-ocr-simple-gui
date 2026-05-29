from pathlib import Path

from scripts.behavior_coverage import scan_cited, scan_declared


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
