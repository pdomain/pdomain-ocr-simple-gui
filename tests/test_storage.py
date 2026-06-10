"""Tests for pdomain_ocr_simple_gui.storage — sidecar IO helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import (
    delete_project,
    get_project_dir,
    list_projects,
    read_page_sidecar,
    read_project,
    write_combined_txt,
    write_page_sidecar,
    write_project,
    write_txt,
)


def _make_spec(tmp_path: Path) -> ProjectSpec:
    return ProjectSpec(
        project_id="test-proj-id-001",
        name="Test Project",
        source_path=str(tmp_path / "source"),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _make_status() -> ProjectStatus:
    return ProjectStatus(
        project_id="test-proj-id-001",
        state="succeeded",
        page_count=2,
        pages_done=2,
        pages=[
            PageResult(page_idx=0, page_name="page_001.png", state="succeeded", text_preview="Hello"),
            PageResult(page_idx=1, page_name="page_002.png", state="succeeded", text_preview="World"),
        ],
    )


class TestGetProjectDir:
    def test_returns_path_under_root(self, projects_root: Path) -> None:
        p = get_project_dir("my-id")
        assert p == projects_root / "my-id"

    def test_falls_back_to_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When env var is unset, get_project_dir returns a path under the default root."""
        monkeypatch.delenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", raising=False)
        p = get_project_dir("some-id")
        # Must be a valid path under some root (not empty, ends with the id)
        assert p.name == "some-id"
        assert p.parent.name  # parent is non-empty (the default root stem)


class TestWriteReadProject:
    def test_round_trip(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        restored_spec, restored_status = read_project("test-proj-id-001")
        assert restored_spec == spec
        assert restored_status == status

    def test_project_json_created(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        proj_dir = projects_root / "test-proj-id-001"
        assert (proj_dir / "project.json").exists()

    def test_read_missing_raises(self, projects_root: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_project("nonexistent-id")


class TestPageSidecar:
    def test_write_read_round_trip(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)

        page_data = {"page_idx": 0, "words": ["Hello", "World"], "confidence": 0.95}
        write_page_sidecar(spec, 0, page_data)

        restored = read_page_sidecar(spec, 0)
        assert restored == page_data

    def test_sidecar_file_created(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_page_sidecar(spec, 0, {"page_idx": 0})
        pages_dir = projects_root / "test-proj-id-001" / "pages"
        assert (pages_dir / "page_001.png.json").exists()

    def test_read_missing_page_raises(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        with pytest.raises(FileNotFoundError):
            read_page_sidecar(spec, 99)


class TestWriteTxt:
    def test_write_txt(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        write_txt(spec, 0, "Hello page 0")
        txt_path = projects_root / "test-proj-id-001" / "pages" / "page_001.png.txt"
        assert txt_path.exists()
        assert txt_path.read_text() == "Hello page 0"

    def test_write_txt_out_of_range_raises(self, projects_root: Path, tmp_path: Path) -> None:
        """write_txt for an out-of-range page index raises FileNotFoundError."""
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        with pytest.raises(FileNotFoundError):
            write_txt(spec, 99, "should not be written")


class TestWriteCombinedTxt:
    def test_combined_txt_concatenates(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_txt(spec, 0, "Page one text")
        write_txt(spec, 1, "Page two text")
        write_combined_txt(spec, status)
        combined = (projects_root / "test-proj-id-001" / "combined.txt").read_text()
        assert "Page one text" in combined
        assert "Page two text" in combined

    def test_combined_txt_with_empty_page_text(self, projects_root: Path, tmp_path: Path) -> None:
        """Pages with empty text are included — separator is still correct."""
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_txt(spec, 0, "")
        write_txt(spec, 1, "Page two text")
        write_combined_txt(spec, status)
        combined = (projects_root / "test-proj-id-001" / "combined.txt").read_text()
        # The non-empty page must appear; the empty page contributes an empty string
        assert "Page two text" in combined


class TestListProjects:
    def test_empty_when_no_projects(self, projects_root: Path) -> None:
        assert list_projects() == []

    def test_lists_written_projects(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        results = list_projects()
        assert len(results) == 1
        assert results[0][0].project_id == "test-proj-id-001"

    def test_corrupt_project_json_is_skipped_gracefully(self, projects_root: Path, tmp_path: Path) -> None:
        """A project.json with invalid JSON is skipped; listing must not raise."""
        # Write a valid project first
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())

        # Add a corrupt sibling directory
        corrupt_dir = projects_root / "corrupt-proj-zzz"
        corrupt_dir.mkdir()
        (corrupt_dir / "project.json").write_text("this is not json {{{")

        results = list_projects()
        # The valid project is still returned; the corrupt one is silently skipped
        ids = [s.project_id for s, _ in results]
        assert "test-proj-id-001" in ids
        assert "corrupt-proj-zzz" not in ids

    def test_multiple_projects_returned_in_stable_order(self, projects_root: Path, tmp_path: Path) -> None:
        """Multiple projects are returned in a stable (sorted) order."""
        from datetime import UTC, datetime

        specs = [
            ProjectSpec(
                project_id=pid,
                name=f"Project {pid}",
                source_path=str(tmp_path / "source"),
                output_dir=str(tmp_path / "output"),
                engine="doctr",
                language="en",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                last_opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            for pid in ["proj-aaa", "proj-bbb", "proj-ccc"]
        ]
        status_base = ProjectStatus(
            project_id="placeholder",
            state="succeeded",
            page_count=0,
            pages_done=0,
            pages=[],
        )
        for sp in specs:
            write_project(sp, ProjectStatus(**{**status_base.model_dump(), "project_id": sp.project_id}))

        results = list_projects()
        returned_ids = [s.project_id for s, _ in results]
        # All three appear in sorted order
        assert returned_ids == sorted(returned_ids)
        assert set(returned_ids) == {"proj-aaa", "proj-bbb", "proj-ccc"}


class TestDeleteProject:
    def test_delete_removes_dir(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        proj_dir = get_project_dir("test-proj-id-001")
        assert proj_dir.exists()
        delete_project("test-proj-id-001")
        assert not proj_dir.exists()

    def test_delete_missing_is_noop(self, projects_root: Path) -> None:
        # Should not raise
        delete_project("does-not-exist")


class TestListProjectsNoFiltering:
    """list_projects() must return EVERY project in the active root.

    There is no runtime test-job filter: separation of test jobs from real
    jobs is by *location* (isolated data roots enforced by the test
    isolation fixture + conftest guard), never by inspecting project ids or
    source paths at listing time.  This guards against regressing to a
    runtime filter that would hide legitimately-created jobs.
    """

    def _write(self, *, pid: str, source_path: str) -> None:
        spec = ProjectSpec(
            project_id=pid,
            name="job",
            source_path=source_path,
            output_dir="",
            engine="doctr",
            language="en",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_opened_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        status = ProjectStatus(project_id=pid, state="succeeded", page_count=0, pages_done=0, pages=[])
        write_project(spec, status)

    def test_test_prefixed_dir_is_listed(self, projects_root: Path, tmp_path: Path) -> None:
        """A project id matching the test-job prefix is NOT filtered out."""
        from pdomain_ocr_simple_gui._testjobs import TEST_JOB_PREFIX

        prefixed_id = TEST_JOB_PREFIX + "abc"
        self._write(pid=prefixed_id, source_path=str(tmp_path / "source"))

        returned_ids = [s.project_id for s, _ in list_projects()]
        assert prefixed_id in returned_ids

    def test_uuid_job_with_pytest_tmp_source_is_listed(self, projects_root: Path, tmp_path: Path) -> None:
        """A UUID job whose source is under /tmp/pytest-* is NOT filtered out."""
        leaked_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self._write(pid=leaked_id, source_path="/tmp/pytest-of-vscode/pytest-411/test_e2e0/source")
        real_id = "real-uuid-1234"
        self._write(pid=real_id, source_path="/home/user/scans/real_source")

        returned_ids = [s.project_id for s, _ in list_projects()]
        assert leaked_id in returned_ids
        assert real_id in returned_ids


class TestIsTestJobAllPrefixes:
    """is_test_job() must return True for every known e2e fixture prefix."""

    def test_all_known_prefixes_are_test_jobs(self) -> None:
        """Every prefix in TEST_JOB_PREFIXES is recognised by is_test_job()."""
        from pdomain_ocr_simple_gui._testjobs import TEST_JOB_PREFIXES, is_test_job

        for prefix in TEST_JOB_PREFIXES:
            assert is_test_job(prefix + "abc123"), f"is_test_job returned False for prefix {prefix!r}"

    def test_real_uuid_is_not_a_test_job(self) -> None:
        """A plain UUID-like id is not a test job."""
        from pdomain_ocr_simple_gui._testjobs import is_test_job

        assert not is_test_job("a1b2c3d4-1234-5678-abcd-ef0123456789")

    def test_non_prefixed_id_is_not_a_test_job(self) -> None:
        """A regular non-prefixed id is not a test job."""
        from pdomain_ocr_simple_gui._testjobs import is_test_job

        assert not is_test_job("real-job-unique-77")


class TestAtomicWrites:
    """JSON writers must be atomic: tmp file + os.replace, never truncate-in-place.

    Regression for the e2e flake where an external reader (the Playwright test
    process) read project.json mid-rewrite and got an empty file — write_text
    truncates before writing. Atomic replace guarantees readers only ever see
    a complete previous or complete new snapshot.
    """

    def test_write_text_atomic_writes_content(self, tmp_path: Path) -> None:
        from pdomain_ocr_simple_gui import storage

        target = tmp_path / "out.json"
        storage.write_text_atomic(target, '{"k": 1}')
        assert target.read_text(encoding="utf-8") == '{"k": 1}'

    def test_write_text_atomic_overwrites_existing(self, tmp_path: Path) -> None:
        from pdomain_ocr_simple_gui import storage

        target = tmp_path / "out.json"
        target.write_text("old")
        storage.write_text_atomic(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_write_text_atomic_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        from pdomain_ocr_simple_gui import storage

        target = tmp_path / "out.json"
        storage.write_text_atomic(target, "data")
        assert [p.name for p in tmp_path.iterdir()] == ["out.json"]

    def test_write_text_atomic_replaces_complete_content_onto_final_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """os.replace must be the publish step: src is a same-dir tmp file whose
        content is already complete at replace time."""
        import os as os_mod

        from pdomain_ocr_simple_gui import storage

        real_replace = os_mod.replace
        observed: list[tuple[str, str, str]] = []

        def recording_replace(src: str | Path, dst: str | Path) -> None:
            observed.append((str(src), str(dst), Path(src).read_text(encoding="utf-8")))
            real_replace(src, dst)

        monkeypatch.setattr("pdomain_ocr_simple_gui.storage.os.replace", recording_replace)
        target = tmp_path / "out.json"
        storage.write_text_atomic(target, '{"complete": true}')

        assert len(observed) == 1
        src, dst, content_at_replace = observed[0]
        assert dst == str(target)
        assert Path(src).parent == tmp_path  # tmp file in same dir → same filesystem
        assert content_at_replace == '{"complete": true}'

    def test_write_text_atomic_cleans_tmp_when_replace_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pdomain_ocr_simple_gui import storage

        def failing_replace(src: str | Path, dst: str | Path) -> None:
            raise OSError("simulated replace failure")

        monkeypatch.setattr("pdomain_ocr_simple_gui.storage.os.replace", failing_replace)
        target = tmp_path / "out.json"
        with pytest.raises(OSError, match="simulated replace failure"):
            storage.write_text_atomic(target, "data")
        assert list(tmp_path.iterdir()) == []  # no tmp file lingers

    def _recording_replace(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
        """Patch storage's os.replace with a recorder; return the call log (dst, content)."""
        import os as os_mod

        real_replace = os_mod.replace
        observed: list[tuple[str, str]] = []

        def recording_replace(src: str | Path, dst: str | Path) -> None:
            observed.append((str(dst), Path(src).read_text(encoding="utf-8")))
            real_replace(src, dst)

        monkeypatch.setattr("pdomain_ocr_simple_gui.storage.os.replace", recording_replace)
        return observed

    def test_write_project_publishes_via_replace(
        self, projects_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as json_mod

        observed = self._recording_replace(monkeypatch)
        write_project(_make_spec(tmp_path), _make_status())

        proj_file = projects_root / "test-proj-id-001" / "project.json"
        assert any(dst == str(proj_file) for dst, _ in observed)
        # Content was complete, valid JSON at publish time.
        for dst, content in observed:
            if dst == str(proj_file):
                assert json_mod.loads(content)["spec"]["project_id"] == "test-proj-id-001"

    def test_write_page_sidecar_publishes_via_replace(
        self, projects_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as json_mod

        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        observed = self._recording_replace(monkeypatch)
        write_page_sidecar(spec, 0, {"words": []})

        sidecar = projects_root / "test-proj-id-001" / "pages" / "page_001.png.json"
        matches = [content for dst, content in observed if dst == str(sidecar)]
        assert matches and json_mod.loads(matches[0]) == {"words": []}

    def test_write_output_page_files_json_publishes_via_replace(
        self, projects_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as json_mod

        from pdomain_ocr_simple_gui.storage import write_output_page_files

        spec = _make_spec(tmp_path)
        observed = self._recording_replace(monkeypatch)
        write_output_page_files(spec, 0, "page_001.png", "hello", {"words": []})

        mirror = Path(spec.output_dir) / "page_001.json"
        matches = [content for dst, content in observed if dst == str(mirror)]
        assert matches and json_mod.loads(matches[0]) == {"words": []}
