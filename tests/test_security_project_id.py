"""Security regression tests — project_id path traversal.

Verifies that encoded and raw traversal sequences in project_id are
rejected at the API boundary before any filesystem operation occurs.

Attack path (GH issue #16):
  DELETE /api/jobs/%2e  →  _PROJECTS_ROOT / "." == _PROJECTS_ROOT
                        →  shutil.rmtree(_PROJECTS_ROOT)   ← deletes everything

HTTPX URL normalisation note:
  httpx normalises RFC 3986 dot segments in URL paths before sending:
    /api/jobs/./  →  /api/jobs/
    /api/jobs/../  →  /api/
  So raw "." and ".." segments never reach the route handler via a
  standard HTTP client — they are resolved away at the transport layer.
  Percent-encoded variants (%2e, %2e%2e) survive that normalisation and
  MUST be rejected by the route handler (FastAPI URL-decodes path params
  before passing them to the handler, so "%2e" arrives as ".").

Two-layer strategy tested here:
  1. Route-layer tests: send requests that DO reach the handler and must
     get 4xx (encoded dots, slashes-in-project-id, null bytes).
  2. Unit tests on validate_project_id: exercise raw ".", "..", slash, etc.
     directly — the function is the last-resort guard if httpx normalisation
     is ever bypassed.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.storage import validate_project_id


@pytest.fixture
async def secured_client(tmp_path, monkeypatch):
    """Client with an isolated tmp project store + a sentinel above the root.

    Layout:
        tmp_path/
            sentinel.txt          ← must NEVER be deleted by the API
            projects/             ← _PROJECTS_ROOT (monkeypatched)
                legit-project/    ← pre-seeded so GET/DELETE can reach storage
                    project.json
    """
    import json

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    # Sentinel above the project root — its presence proves no upward escape
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("do not delete")

    # Pre-seed a legitimate project so the storage layer has something to read
    legit_id = "legit-project-abc123"
    legit_dir = root / legit_id
    legit_dir.mkdir()
    project_data = {
        "spec": {
            "project_id": legit_id,
            "name": "Legit",
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
            "project_id": legit_id,
            "state": "succeeded",
            "page_count": 0,
            "pages_done": 0,
            "pages": [],
        },
    }
    (legit_dir / "project.json").write_text(json.dumps(project_data))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, root, sentinel


# ---------------------------------------------------------------------------
# IDs that httpx will send AS-IS (no path normalization) and that must reach
# the route handler, which must then reject them with 4xx.
#
# httpx normalises RFC-3986 dot segments: "./" and "../" in paths are resolved
# before the request is sent, so raw "." and ".." path segments never reach
# the server via a conformant HTTP client.  Only percent-encoded forms bypass
# client normalisation; FastAPI then decodes them in the route handler.
# ---------------------------------------------------------------------------
ROUTE_TRAVERSAL_IDS = [
    # Percent-encoded dot segments — bypass httpx normalisation; decoded by FastAPI
    "%2e",  # decoded to "."
    "%2e%2e",  # decoded to ".."
    # Null byte — must never reach the filesystem
    "abc%00def",  # decoded null byte
    # Note: "%2f" (encoded slash) is NOT in this list because httpx decodes it to
    # "/" before sending, causing the URL to route to a different path segment
    # pattern entirely (never reaches the {project_id} route handler as a single
    # parameter).  The validate_project_id unit tests cover this via UNIT_TRAVERSAL_IDS.
]

# For the pages routes the project_id segment sits between two slashes in a
# multi-segment path, so some forms route differently.  Use the same set.
ROUTE_TRAVERSAL_IDS_PAGES = ROUTE_TRAVERSAL_IDS


# ---------------------------------------------------------------------------
# Unit-level: validate_project_id must reject ALL of these directly
# (covers the raw forms that httpx would normalise away before sending)
# ---------------------------------------------------------------------------
UNIT_TRAVERSAL_IDS = [
    ".",
    "..",
    "./subdir",
    "../sibling",
    "good/../evil",
    "good/../../escape",
    # Percent-encoded forms (already decoded before validate_project_id is called)
    # listed here as their decoded equivalents — the route layer decodes them first
    # Null byte
    "abc\x00def",
    # Forward slash in the middle
    "legit/evil",
    # Backslash
    "legit\\evil",
    # Empty string
    "",
]


class TestValidateProjectIdUnit:
    """Direct unit tests of validate_project_id — covers all bad forms."""

    @pytest.mark.parametrize("bad_id", UNIT_TRAVERSAL_IDS)
    def test_rejects_traversal_id(self, bad_id: str) -> None:
        with pytest.raises(ValueError):
            validate_project_id(bad_id)

    def test_accepts_uuid_style(self) -> None:
        validate_project_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    def test_accepts_alphanumeric_with_dash_underscore(self) -> None:
        for valid_id in ["abc123", "abc-def", "ABC_123", "legit-project-abc123"]:
            validate_project_id(valid_id)  # must not raise


class TestDeleteJobTraversal:
    """DELETE /api/jobs/{project_id} — the primary attack vector."""

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS)
    async def test_rejects_traversal_id(self, secured_client, bad_id: str) -> None:
        """DELETE with a traversal project_id must return 4xx."""
        client, _root, _sentinel = secured_client
        resp = await client.delete(f"/api/jobs/{bad_id}")
        assert resp.status_code in (400, 404, 422), (
            f"Expected 4xx for DELETE {bad_id!r}, got {resp.status_code}"
        )

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS)
    async def test_sentinel_survives_traversal_attempt(self, secured_client, bad_id: str) -> None:
        """Sentinel file above the project root must not be deleted."""
        client, _root, sentinel = secured_client
        await client.delete(f"/api/jobs/{bad_id}")
        assert sentinel.exists(), f"Sentinel was deleted — traversal escaped project root for id={bad_id!r}"

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS)
    async def test_project_root_survives_traversal_attempt(self, secured_client, bad_id: str) -> None:
        """The projects root directory itself must survive a traversal attempt."""
        client, root, _sentinel = secured_client
        await client.delete(f"/api/jobs/{bad_id}")
        assert root.exists(), f"_PROJECTS_ROOT was deleted — traversal succeeded for id={bad_id!r}"


class TestGetJobTraversal:
    """GET /api/jobs/{project_id} — read-path traversal."""

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS)
    async def test_rejects_traversal_id(self, secured_client, bad_id: str) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.get(f"/api/jobs/{bad_id}")
        assert resp.status_code in (400, 404, 422), f"Expected 4xx for GET {bad_id!r}, got {resp.status_code}"


class TestRerunJobTraversal:
    """POST /api/jobs/{project_id}/rerun — traversal via rerun."""

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS)
    async def test_rejects_traversal_id(self, secured_client, bad_id: str) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.post(f"/api/jobs/{bad_id}/rerun")
        assert resp.status_code in (400, 404, 422), (
            f"Expected 4xx for RERUN {bad_id!r}, got {resp.status_code}"
        )


class TestGetPageTraversal:
    """GET /api/pages/{project_id}/{page_idx} — traversal via pages routes."""

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS_PAGES)
    async def test_rejects_traversal_id(self, secured_client, bad_id: str) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.get(f"/api/pages/{bad_id}/0")
        assert resp.status_code in (400, 404, 422), (
            f"Expected 4xx for GET page {bad_id!r}, got {resp.status_code}"
        )


class TestPutPageTextTraversal:
    """PUT /api/pages/{project_id}/{page_idx}/text — traversal via page text save."""

    @pytest.mark.parametrize("bad_id", ROUTE_TRAVERSAL_IDS_PAGES)
    async def test_rejects_traversal_id(self, secured_client, bad_id: str) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.put(f"/api/pages/{bad_id}/0/text", json={"text": "hello"})
        assert resp.status_code in (400, 404, 422), (
            f"Expected 4xx for PUT text {bad_id!r}, got {resp.status_code}"
        )


class TestLegitProjectIdStillWorks:
    """Sanity: valid UUID-style project IDs must still work after the fix."""

    async def test_get_legit_project(self, secured_client) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.get("/api/jobs/legit-project-abc123")
        assert resp.status_code == 200

    async def test_delete_legit_project(self, secured_client) -> None:
        client, _root, _sentinel = secured_client
        resp = await client.delete("/api/jobs/legit-project-abc123")
        assert resp.status_code == 200

    async def test_alphanumeric_dashes_underscores_allowed(self, secured_client) -> None:
        """Allowlist must permit A-Z a-z 0-9 - _ (UUID chars + common separators)."""
        client, _root, _sentinel = secured_client
        for valid_id in [
            "abc123",
            "abc-def",
            "ABC_123",
            "a1b2-c3d4-e5f6",
        ]:
            resp = await client.get(f"/api/jobs/{valid_id}")
            # 404 is fine (no project); 400/422 would mean we over-rejected
            assert resp.status_code in (200, 404), (
                f"Valid project_id {valid_id!r} was wrongly rejected with {resp.status_code}"
            )
