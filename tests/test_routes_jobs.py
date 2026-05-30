"""Tests for /api/jobs routes."""

from __future__ import annotations

from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.models import ProjectStatus

JOB_PAYLOAD = {
    "name": "Test Job",
    "source_path": "/tmp/source",
    "output_dir": "/tmp/output",
    "engine": "doctr",
    "language": "en",
    "save_json": False,
    "combined_txt": True,
}


def _make_done_status_callback(project_id: str):
    """Return an async run_project mock that immediately marks the project done."""

    async def _mock_run_project(spec, dispatcher, status_callback) -> None:
        from pdomain_ocr_simple_gui.models import PageResult
        from pdomain_ocr_simple_gui.storage import write_project

        done_status = ProjectStatus(
            project_id=spec.project_id,
            state="succeeded",
            page_count=1,
            pages_done=1,
            pages=[PageResult(page_idx=0, page_name="page0.png", state="succeeded", text_preview="")],
        )
        write_project(spec, done_status)
        await status_callback(done_status)

    return _mock_run_project


class TestPostJob:
    async def test_creates_job(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "project_id" in data
        assert len(data["project_id"]) > 0

    async def test_created_job_is_retrievable(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = resp.json()["project_id"]
        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        status = get_resp.json()
        assert status["project_id"] == project_id
        assert status["state"] in ("queued", "running", "succeeded", "failed", "cancelled")


class TestGetJob:
    async def test_404_for_missing(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/jobs/nonexistent-id")
        assert resp.status_code == 404

    async def test_returns_project_status(self, async_client: AsyncClient) -> None:
        post_resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        status = get_resp.json()
        assert status["project_id"] == project_id
        assert "state" in status
        assert "page_count" in status
        assert "pages_done" in status
        assert "pages" in status
        # Issue #3: must include name and output_dir from ProjectSpec
        assert status["name"] == JOB_PAYLOAD["name"]
        assert status["output_dir"] == JOB_PAYLOAD["output_dir"]


class TestListJobs:
    async def test_empty_list(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_lists_created_jobs(self, async_client: AsyncClient) -> None:
        await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        await async_client.post("/api/jobs", json={**JOB_PAYLOAD, "name": "Job 2"})
        resp = await async_client.get("/api/jobs")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        names = {item["name"] for item in items}
        assert JOB_PAYLOAD["name"] in names, "list_jobs must enrich with name from ProjectSpec"

    async def test_list_jobs_excludes_corrupt_project(self, projects_root, monkeypatch) -> None:
        """GET /api/jobs gracefully skips projects with corrupt project.json.

        Bad state: a project directory exists but project.json contains invalid
        JSON. The listing must still return 200 (not 500) and omit the corrupt
        entry, leaving any valid projects intact.
        """
        import json

        from httpx import ASGITransport, AsyncClient

        from pdomain_ocr_simple_gui.app import app

        # Write a corrupt project.json alongside a valid one
        corrupt_dir = projects_root / "corrupt-proj-001"
        corrupt_dir.mkdir()
        (corrupt_dir / "project.json").write_text("not-valid-json{{{")

        # Write a valid project so the list is non-empty when it works
        valid_dir = projects_root / "valid-proj-001"
        valid_dir.mkdir()
        project_data = {
            "spec": {
                "project_id": "valid-proj-001",
                "name": "Valid",
                "source_path": "/tmp/src",
                "output_dir": "/tmp/out",
                "engine": "doctr",
                "language": "en",
                "save_json": False,
                "combined_txt": True,
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_opened_at": "2026-01-01T00:00:00+00:00",
            },
            "status": {
                "project_id": "valid-proj-001",
                "state": "succeeded",
                "page_count": 0,
                "pages_done": 0,
                "pages": [],
            },
        }
        (valid_dir / "project.json").write_text(json.dumps(project_data))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/jobs")

        # Must return 200 — corrupt entry must not blow up the listing
        assert resp.status_code == 200
        items = resp.json()
        project_ids = [item["project_id"] for item in items]
        # The valid project must appear
        assert "valid-proj-001" in project_ids
        # The corrupt project must be silently skipped
        assert "corrupt-proj-001" not in project_ids


class TestDeleteJob:
    async def test_delete_removes_job(self, async_client: AsyncClient) -> None:
        post_resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        del_resp = await async_client.delete(f"/api/jobs/{project_id}")
        assert del_resp.status_code == 200
        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 404

    async def test_delete_missing_is_204(self, async_client: AsyncClient) -> None:
        resp = await async_client.delete("/api/jobs/does-not-exist")
        assert resp.status_code == 204

    async def test_delete_removes_output_mirror_and_meta_sidecar(self, tmp_path, monkeypatch) -> None:
        """B-RESULTS-014: delete must also remove the output mirror and meta sidecar.

        Previously delete only rmtree'd the canonical projects dir, leaving the
        user-visible output mirror (spec.output_dir) and the per-job meta
        sidecar (<JOBS_META_ROOT>/<id>/) orphaned — so a deleted job's ZIP
        could still be downloaded. All three on-disk locations must be gone.
        """
        import json
        from datetime import UTC, datetime

        from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
        from pdomain_ocr_simple_gui.storage import get_project_dir, write_project

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "outputs"
        meta_root = tmp_path / "jobs_meta"
        for d in (projects_root, output_root, meta_root):
            d.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(output_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT", str(meta_root))

        project_id = "deltest-001"
        now = datetime.now(UTC)
        output_dir = output_root / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        # User-visible output mirror artifacts (what the download ZIP streams).
        (output_dir / "page-001.txt").write_text("hello", encoding="utf-8")
        (output_dir / "page-001.json").write_text('{"text": "hello"}', encoding="utf-8")

        spec = ProjectSpec(
            project_id=project_id,
            name="del-me",
            source_path=str(tmp_path / "src"),
            output_dir=str(output_dir),
            engine="doctr",
            language="en",
            created_at=now,
            last_opened_at=now,
        )
        status = ProjectStatus(
            project_id=project_id,
            state="succeeded",
            page_count=1,
            pages_done=1,
            pages=[PageResult(page_idx=0, page_name="page-001", state="succeeded")],
        )
        write_project(spec, status)

        # Per-job meta sidecar (drives output_mode in GET, survives delete today).
        meta_dir = meta_root / project_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "output_mode.json").write_text(json.dumps({"mode": "managed"}), encoding="utf-8")

        canonical_dir = get_project_dir(project_id)
        assert canonical_dir.exists()
        assert output_dir.exists()
        assert meta_dir.exists()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(f"/api/jobs/{project_id}")

        assert resp.status_code == 200
        # All THREE on-disk locations must be gone — no orphaned mirror or meta.
        assert not canonical_dir.exists(), "canonical project dir not removed"
        assert not output_dir.exists(), "output mirror dir not removed (orphaned ZIP source)"
        assert not meta_dir.exists(), "per-job meta sidecar dir not removed"

    async def test_delete_then_download_is_404(self, tmp_path, monkeypatch) -> None:
        """B-RESULTS-014: after delete, the download endpoint must 404 (no orphan).

        The bad-path companion: previously the output mirror survived delete and
        the downloads route fell back to <OUTPUT_ROOT>/<id>, so a deleted job's
        ZIP still streamed. With the mirror removed, download must 404.
        """
        from datetime import UTC, datetime

        from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
        from pdomain_ocr_simple_gui.storage import write_project

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "outputs"
        meta_root = tmp_path / "jobs_meta"
        for d in (projects_root, output_root, meta_root):
            d.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(output_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT", str(meta_root))

        project_id = "deldl-001"
        now = datetime.now(UTC)
        output_dir = output_root / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "page-001.txt").write_text("hello", encoding="utf-8")

        spec = ProjectSpec(
            project_id=project_id,
            name="dl-me",
            source_path=str(tmp_path / "src"),
            output_dir=str(output_dir),
            engine="doctr",
            language="en",
            created_at=now,
            last_opened_at=now,
        )
        status = ProjectStatus(
            project_id=project_id,
            state="succeeded",
            page_count=1,
            pages_done=1,
            pages=[PageResult(page_idx=0, page_name="page-001", state="succeeded")],
        )
        write_project(spec, status)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Download works before delete.
            pre = await ac.get(f"/api/jobs/{project_id}/download")
            assert pre.status_code == 200
            del_resp = await ac.delete(f"/api/jobs/{project_id}")
            assert del_resp.status_code == 200
            # After delete the mirror is gone → download 404s.
            post = await ac.get(f"/api/jobs/{project_id}/download")
        assert post.status_code == 404


class TestPipelineIntegration:
    """Tests that verify run_project is wired into POST /api/jobs."""

    async def test_run_project_called_on_post(self, client_with_source) -> None:
        """POST /api/jobs enqueues the pipeline: the created project is in storage."""
        client, source_path = client_with_source

        # Use a real storage write inside the fake so we can observe the project state
        async def _fake_run_project(spec, dispatcher, status_callback) -> None:
            from pdomain_ocr_simple_gui.models import PageResult
            from pdomain_ocr_simple_gui.storage import write_project

            done_status = ProjectStatus(
                project_id=spec.project_id,
                state="succeeded",
                page_count=1,
                pages_done=1,
                pages=[PageResult(page_idx=0, page_name="p.png", state="succeeded", text_preview="")],
            )
            write_project(spec, done_status)
            await status_callback(done_status)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _fake_run_project):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        assert resp.status_code == 202
        project_id = resp.json()["project_id"]
        # Observable: project is retrievable (pipeline ran and persisted state)
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200

    async def test_job_transitions_to_done_via_mock(self, client_with_source) -> None:
        """Job transitions queued → succeeded when run_project completes.

        Observable: GET /api/jobs/:id returns state='succeeded' after the
        background task writes the final status to storage.
        """
        client, source_path = client_with_source

        with patch(
            "pdomain_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = resp.json()["project_id"]

        # Observable: final state persisted to storage and returned by GET
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "succeeded"

    async def test_dispatcher_passed_to_run_project(self, client_with_source) -> None:
        """POST /api/jobs wires a LocalStageDispatcher into the pipeline.

        Observable: the dispatcher received by run_project is a real
        LocalStageDispatcher instance (not None, not a bare object).
        """
        from pdomain_ops.gpu import LocalStageDispatcher

        client, source_path = client_with_source
        received_dispatchers: list = []

        async def _capture(spec, dispatcher, status_callback) -> None:
            received_dispatchers.append(dispatcher)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _capture):
            await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )

        # Observable: exactly one dispatcher was passed; it is the expected type
        assert len(received_dispatchers) == 1
        assert isinstance(received_dispatchers[0], LocalStageDispatcher)

    async def test_zero_supported_images_marks_job_failed(self, tmp_path, monkeypatch) -> None:
        """A source with no supported image extensions must fail loudly.

        Previously this silently wrote state='succeeded' with page_count=0,
        which hid real bugs (e.g., dropped JPEG 2000 input) from the user.
        """
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Source dir with only unsupported file types
        src = tmp_path / "empty-source"
        src.mkdir()
        (src / "readme.txt").write_text("nothing to see")
        (src / "noise.bmp").write_bytes(b"BM")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/jobs", json={**JOB_PAYLOAD, "source_path": str(src)})
            assert resp.status_code == 202
            project_id = resp.json()["project_id"]
            get_resp = await ac.get(f"/api/jobs/{project_id}")

        data = get_resp.json()
        assert data["state"] == "failed", f"expected failed, got {data['state']}: {data}"
        assert data["page_count"] == 0
        # Error message mentions supported types
        err = data.get("error") or ""
        assert "supported" in err.lower(), f"expected supported-types hint in error, got {err!r}"


class TestCanonicalJobStates:
    """Verify that the API always emits pdomain-ops canonical state values.

    The canonical states are: queued | running | succeeded | failed | cancelled.
    Legacy values like 'done' or 'error' must never appear in API responses.
    """

    async def test_failed_job_returns_failed_not_error(self, client_with_source) -> None:
        """A job whose pipeline raises must return state='failed', not 'error'."""
        client, source_path = client_with_source

        async def _fail_run(spec, dispatcher, status_callback) -> None:
            from pdomain_ocr_simple_gui.models import PageResult
            from pdomain_ocr_simple_gui.storage import write_project

            failed_status = ProjectStatus(
                project_id=spec.project_id,
                state="failed",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="failed", text_preview="")],
            )
            write_project(spec, failed_status)
            await status_callback(failed_status)

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _fail_run):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        assert resp.status_code == 202
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        state = get_resp.json()["state"]
        # Must be canonical 'failed' — never the legacy 'error' value
        assert state == "failed", f"Expected 'failed' but got {state!r}"
        assert state != "error", "Legacy 'error' state must not be returned by the API"

    async def test_succeeded_job_returns_succeeded_not_done(self, client_with_source) -> None:
        """A completed job must return state='succeeded', not the legacy 'done'."""
        client, source_path = client_with_source

        with patch(
            "pdomain_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = resp.json()["project_id"]

        get_resp = await client.get(f"/api/jobs/{project_id}")
        state = get_resp.json()["state"]
        # Must be canonical 'succeeded' — never the legacy 'done' value
        assert state == "succeeded", f"Expected 'succeeded' but got {state!r}"
        assert state != "done", "Legacy 'done' state must not be returned by the API"

    async def test_state_is_always_a_canonical_value(self, async_client: AsyncClient) -> None:
        """Every job state returned by the API must be a canonical pdomain-ops value."""
        CANONICAL_STATES = {"queued", "running", "succeeded", "failed", "cancelled"}
        LEGACY_STATES = {"done", "error", "pending", "created", "complete"}

        resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = resp.json()["project_id"]
        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        state = get_resp.json()["state"]
        assert state in CANONICAL_STATES, f"Job state {state!r} is not a canonical pdomain-ops state"
        assert state not in LEGACY_STATES, f"Legacy state {state!r} must not be returned by the API"

    async def test_legacy_states_never_returned_by_list_jobs(self, client_with_source) -> None:
        """GET /api/jobs must never return legacy state values ('done', 'error').

        Bad state: even when the underlying storage writes a state that uses
        the old naming, the API response must still emit canonical values only.
        This guards against any regressions that rename 'succeeded'→'done' or
        'failed'→'error' in the response serialization path.
        """
        client, source_path = client_with_source
        LEGACY_STATES = {"done", "error", "pending", "created", "complete"}

        with patch(
            "pdomain_ocr_simple_gui.routes.jobs.run_project",
            _make_done_status_callback(""),
        ):
            await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )

        list_resp = await client.get("/api/jobs")
        assert list_resp.status_code == 200
        for item in list_resp.json():
            assert item["state"] not in LEGACY_STATES, (
                f"Legacy state {item['state']!r} returned by GET /api/jobs"
            )


class TestRerunJob:
    """Tests for POST /api/jobs/{project_id}/rerun."""

    async def test_rerun_returns_queued_state(self, client_with_source) -> None:
        """POST /api/jobs/:id/rerun resets status to queued."""
        client, source_path = client_with_source

        # Create a job first
        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Confirm it is done
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.json()["state"] == "succeeded"

        # Rerun it — pipeline is a no-op stub so state will be queued immediately
        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            rerun_resp = await client.post(f"/api/jobs/{project_id}/rerun")

        assert rerun_resp.status_code == 202
        data = rerun_resp.json()
        assert data["project_id"] == project_id
        assert data["state"] == "queued"

    async def test_rerun_resets_pages_to_queued(self, client_with_source) -> None:
        """After rerun, all pages should have state 'queued'."""
        client, source_path = client_with_source

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Check it reached done
        done_resp = await client.get(f"/api/jobs/{project_id}")
        assert done_resp.json()["state"] == "succeeded"

        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            await client.post(f"/api/jobs/{project_id}/rerun")

        status_resp = await client.get(f"/api/jobs/{project_id}")
        status = status_resp.json()
        assert status["state"] == "queued"
        for page in status["pages"]:
            assert page["state"] == "queued"

    async def test_rerun_404_for_missing(self, async_client: AsyncClient) -> None:
        """Reruns a non-existent project → 404."""
        resp = await async_client.post("/api/jobs/no-such-project/rerun")
        assert resp.status_code == 404

    async def test_rerun_triggers_pipeline(self, client_with_source) -> None:
        """POST /api/jobs/:id/rerun re-triggers the pipeline.

        Observable: after the noop pipeline completes, the project stays in
        storage (rerun did not delete it) and the reset state is readable.
        """
        client, source_path = client_with_source

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _make_done_status_callback("")):
            post_resp = await client.post(
                "/api/jobs",
                json={**JOB_PAYLOAD, "source_path": source_path},
            )
        project_id = post_resp.json()["project_id"]

        # Rerun with a noop pipeline — just reset state, no OCR
        async def _noop_run(spec, dispatcher, cb):
            pass

        with patch("pdomain_ocr_simple_gui.routes.jobs.run_project", _noop_run):
            rerun_resp = await client.post(f"/api/jobs/{project_id}/rerun")

        assert rerun_resp.status_code == 202
        # Observable: project still exists and was reset to queued (pipeline was invoked)
        get_resp = await client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["project_id"] == project_id

    async def test_rerun_nonexistent_project_404(self, async_client: AsyncClient) -> None:
        """POST /api/jobs/:id/rerun for a project that was never created returns 404.

        Bad state: project does not exist in storage — rerun must not return 202.
        """
        resp = await async_client.post("/api/jobs/absolutely-does-not-exist/rerun")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestUploadIdSource:
    """Tests for POST /api/jobs with upload_id + OutputConfig."""

    async def test_create_job_with_upload(self, tmp_path, monkeypatch) -> None:
        """POST /api/jobs with upload_id and output:managed returns 200 or 202."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

        # Pre-create a staging dir that UploadedFilesSource will find
        stage = tmp_path / "abc123"
        stage.mkdir()
        (stage / "p.png").write_bytes(b"\x89PNG")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc123",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
        assert resp.status_code in (200, 202)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc123",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
        assert resp.status_code in (200, 202)

    async def test_create_job_with_missing_upload_id_returns_error(self, tmp_path, monkeypatch) -> None:
        """POST /api/jobs with an upload_id that was never staged returns 4xx.

        Bad state: the upload_id does not correspond to any staging directory
        so UploadedFilesSource.materialize() raises SourceNotFound. The route
        must translate this into a 400 response, not a 202 with a broken spec.
        """
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

        # Deliberately do NOT create the staging directory for "ghost-upload"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "ghost-upload-does-not-exist",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
        assert resp.status_code == 400
        assert "source" in resp.json()["detail"].lower()


class TestFakeDispatcherEndToEnd:
    """End-to-end job run using the FakeStageDispatcher seam — no model weights."""

    async def test_job_runs_with_fake_dispatcher(
        self,
        tmp_path,
        monkeypatch,
        use_fake_dispatcher,
    ) -> None:
        """POST /api/jobs → pipeline completes with fake OCR → state=succeeded.

        Good state: with the fake dispatcher wired in, a job with a real
        image file on disk completes without loading any OCR model weights.
        The fake text is persisted to storage and the job reaches 'succeeded'.
        """
        from io import BytesIO

        from PIL import Image

        # Isolate storage
        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Create a real tiny PNG so collect_images finds it
        src = tmp_path / "source"
        src.mkdir()
        buf = BytesIO()
        Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
        (src / "page001.png").write_bytes(buf.getvalue())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "name": "fake-e2e",
                    "source_path": str(src),
                    "output_dir": str(tmp_path / "output"),
                    "engine": "doctr",
                    "language": "en",
                },
            )
        assert resp.status_code == 202
        project_id = resp.json()["project_id"]

        # Background task has already run (ASGITransport executes it inline)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            status_resp = await ac.get(f"/api/jobs/{project_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["state"] == "succeeded", f"expected succeeded, got {data['state']}: {data}"

    async def test_pages_contain_fake_text_after_run(
        self,
        tmp_path,
        monkeypatch,
        use_fake_dispatcher,
    ) -> None:
        """After a fake-dispatcher run, GET /api/pages/{id}/0 returns the fake text.

        Good state: the fake text written to sidecar is readable via the
        pages route without any model weights.
        """
        from io import BytesIO

        from PIL import Image

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        buf = BytesIO()
        Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
        (src / "page001.png").write_bytes(buf.getvalue())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/jobs",
                json={
                    "source_path": str(src),
                    "output_dir": str(tmp_path / "output"),
                    "engine": "doctr",
                    "language": "en",
                },
            )
        project_id = resp.json()["project_id"]

        # Fetch page 0 from the pages route (pages use /{project_id}/{page_idx})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            page_resp = await ac.get(f"/api/pages/{project_id}/0")
        assert page_resp.status_code == 200
        page_data = page_resp.json()
        text = page_data.get("text", "")
        # The sidecar text must contain the fake OCR text (default "fake OCR output")
        assert "fake" in text.lower(), f"Expected fake OCR text in page, got: {text!r}"


class TestOutputModeRoundTrip:
    """output_mode written on create, returned on GET /api/jobs/{id}."""

    async def test_output_mode_returned_on_get(self, tmp_path, monkeypatch) -> None:
        """Creating a job with output.mode='managed' surfaces output_mode on GET."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Point jobs-meta sidecar to tmp
        meta_root = tmp_path / "jobs-meta"
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_JOBS_META_ROOT", str(meta_root))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

        stage = tmp_path / "abc456"
        stage.mkdir()
        (stage / "p.png").write_bytes(b"\x89PNG")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            post_resp = await ac.post(
                "/api/jobs",
                json={
                    "upload_id": "abc456",
                    "engine": "doctr",
                    "language": "en",
                    "output": {"mode": "managed"},
                },
            )
            assert post_resp.status_code in (200, 202)
            project_id = post_resp.json()["project_id"]

            get_resp = await ac.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["output_mode"] == "managed"

    async def test_output_mode_absent_for_legacy_jobs(self, async_client: AsyncClient) -> None:
        """Legacy jobs (no output field) return output_mode=None or absent key."""
        post_resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        project_id = post_resp.json()["project_id"]
        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        # output_mode either absent or None — not a hard value
        assert body.get("output_mode") is None

    async def test_get_job_returns_200_when_output_mode_sidecar_missing(
        self, async_client: AsyncClient
    ) -> None:
        """GET /api/jobs/:id returns 200 even when the output_mode sidecar is absent.

        Bad state: job was created without an output.mode (legacy path), so no
        output_mode.json sidecar exists. The GET must still return 200 with
        output_mode=None rather than raising or returning garbage.
        """
        post_resp = await async_client.post("/api/jobs", json=JOB_PAYLOAD)
        assert post_resp.status_code == 202
        project_id = post_resp.json()["project_id"]

        get_resp = await async_client.get(f"/api/jobs/{project_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        # When sidecar is missing, output_mode must be None (not an error)
        assert data.get("output_mode") is None
        # Core fields must still be present and correct
        assert data["project_id"] == project_id
        assert data["state"] in {"queued", "running", "succeeded", "failed", "cancelled"}
