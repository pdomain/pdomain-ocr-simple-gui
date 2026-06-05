"""FastAPI application for pdomain-ocr-simple-gui."""

from __future__ import annotations

import importlib.resources
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pdomain_ops.gpu.local_stage import LocalStageDispatcher
    from pdomain_ops.suite.prefs import PrefsAdapter

logger = logging.getLogger(__name__)

# Module-level prefs adapter — set during lifespan startup
_prefs_adapter: PrefsAdapter | None = None
# Module-level dispatcher — set during lifespan startup
_dispatcher: LocalStageDispatcher | None = None


def get_prefs_adapter() -> PrefsAdapter | None:
    """Return the current prefs adapter (None before startup)."""
    return _prefs_adapter


def get_dispatcher() -> LocalStageDispatcher | None:
    """Return the current stage dispatcher (None before startup)."""
    return _dispatcher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Wire prefs adapter, stage dispatcher, and suite registration at startup."""
    _ = app
    global _prefs_adapter, _dispatcher  # noqa: PLW0603  # module-level singletons for FastAPI lifespan
    # Warn at startup when source paths are unrestricted.
    from pdomain_ocr_simple_gui.sources.local_path import get_allowlist

    if get_allowlist() is None:
        _msg = (
            "SOURCE_ROOT_ALLOWLIST is not set or empty — "
            + "LocalPathSource will accept any filesystem path. "
            + "Set SOURCE_ROOT_ALLOWLIST to a colon-separated list of allowed roots "
            + "to restrict access."
        )
        logger.warning(_msg)

    try:
        from pdomain_ops.suite.prefs import LocalFilePrefs

        _prefs_adapter = LocalFilePrefs()
    except Exception:  # optional prefs integration — app runs without it
        logger.exception(
            "Failed to initialise prefs adapter; running without prefs",
            extra={"context": "LocalFilePrefs()"},
        )
        _prefs_adapter = None
    if os.environ.get("PDOMAIN_OCR_FAKE_DISPATCHER"):
        logger.warning(
            "PDOMAIN_OCR_FAKE_DISPATCHER is set: using FakeStageDispatcher — OCR output is FAKE. Do not use in production."
        )
        from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

        _dispatcher = FakeStageDispatcher()  # pyright: ignore[reportAssignmentType]
    else:
        try:
            from pdomain_ops.gpu import (
                LocalStageDispatcher,
                register_default_stages,
            )

            _dispatcher = LocalStageDispatcher()
            register_default_stages(_dispatcher)
        except Exception:  # default stages optional — fall back to bare dispatcher
            logger.exception(
                "register_default_stages() failed; falling back to bare LocalStageDispatcher",
                extra={"context": "register_default_stages(_dispatcher)"},
            )
            from pdomain_ops.gpu import LocalStageDispatcher

            _dispatcher = LocalStageDispatcher()
    # Auth startup notice.
    api_token = os.environ.get("PDOMAIN_API_TOKEN", "").strip()
    if not api_token:
        logger.warning(
            "PDOMAIN_API_TOKEN is not set — API auth is DISABLED. Set this env var to enable capability token protection.",
        )

    # Suite registration is handled by bootstrap_spa() in __main__.py before uvicorn.run().
    yield
    _prefs_adapter = None
    _dispatcher = None


_FRONTEND_DIR = Path(__file__).parent / "frontend"
_ALLOWED_SELF_ICON_SIZES = {16, 24, 32, 48, 64, 128, 256}


def create_app() -> FastAPI:
    """Create and return a configured FastAPI application instance."""
    _app = FastAPI(
        title="pdomain-ocr-simple-gui",
        description="Drag-and-drop OCR app",
        version="0.1.0a0",
        lifespan=lifespan,
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Protect suite routes (/api/suite/*) via middleware — they are mounted
    # externally by pdomain_ops.suite.routes and cannot use FastAPI Depends.
    from pdomain_ocr_simple_gui.auth import suite_token_middleware

    _app.add_middleware(BaseHTTPMiddleware, dispatch=suite_token_middleware)

    # Register routes.
    # Imported here (not at module level) to avoid circular imports at collection time.
    from pdomain_ocr_simple_gui.routes.config import router as config_router
    from pdomain_ocr_simple_gui.routes.downloads import router as downloads_router
    from pdomain_ocr_simple_gui.routes.jobs import router as jobs_router
    from pdomain_ocr_simple_gui.routes.pages import router as pages_router
    from pdomain_ocr_simple_gui.routes.prefs import router as prefs_router
    from pdomain_ocr_simple_gui.routes.uploads import router as uploads_router
    from pdomain_ocr_simple_gui.routes.words import router as words_router

    _app.include_router(jobs_router)
    _app.include_router(pages_router)
    _app.include_router(prefs_router)
    _app.include_router(config_router)
    _app.include_router(uploads_router)
    _app.include_router(downloads_router)
    _app.include_router(words_router)

    # Mount suite plumbing routes (/api/suite/*, /api/icons/*, /healthz)
    try:
        from pdomain_ops.suite.routes import (
            mount_routes as _mount_suite_routes,
        )

        _mount_suite_routes(_app)
    except Exception:  # suite plumbing routes optional — app serves without them
        logger.exception(
            "Failed to mount suite plumbing routes; /api/suite/* will be unavailable",
            extra={"context": "mount_routes(_app)"},
        )

    @_app.get("/api/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint."""
        return {"status": "ok"}

    @_app.get("/api/self/icons/{size}")
    async def get_self_icon(size: int) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Serve this app's own icon for the given size (PNG)."""
        if size not in _ALLOWED_SELF_ICON_SIZES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported size {size}. Allowed: {sorted(_ALLOWED_SELF_ICON_SIZES)}",
            )
        icons_pkg = importlib.resources.files("pdomain_ocr_simple_gui") / "icons"
        icon_file = icons_pkg / f"{size}.png"
        try:
            # importlib.resources Traversable has .read_bytes() at runtime; not in the stub protocol
            icon_bytes = icon_file.read_bytes()  # type: ignore[attr-defined]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Icon {size}.png not found") from exc
        return Response(content=icon_bytes, media_type="image/png")

    # Serve static JS/CSS assets — must come before the catch-all route.
    # check_dir=False skips the existence check at startup; missing-assets requests 404 naturally.
    _app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIR / "assets", check_dir=False),
        name="assets",
    )

    # SPA catch-all — React Router owns all non-API paths.
    # MUST be registered last so it never shadows /api/* routes.
    # Root-level static files (e.g. manifest.webmanifest, favicon.ico) are
    # served directly when they exist as real files in the frontend build root.
    # Vite copies frontend/public/ into the build root, so these arrive there.
    @_app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        """Serve static root files or the React SPA index.html.

        Path traversal guard: resolve the candidate path and verify it is
        strictly contained within the frontend directory before serving.
        Percent-encoded separators (e.g. %2f) are decoded by the ASGI layer
        before this handler runs, so a resolve() + is_relative_to() check
        is sufficient to block all traversal variants.
        """
        if full_path and not full_path.startswith("api/"):
            candidate = _FRONTEND_DIR / full_path
            resolved = candidate.resolve()
            frontend_resolved = _FRONTEND_DIR.resolve()
            if (
                resolved.is_file()
                and resolved.is_relative_to(frontend_resolved)
                and not resolved.name.startswith(".")
            ):
                return FileResponse(resolved)
        index = _FRONTEND_DIR / "index.html"
        if not index.exists():
            raise HTTPException(
                status_code=503,
                detail="Frontend not built — run make frontend-build",
            )
        return FileResponse(index)

    return _app


# Module-level singleton for uvicorn and existing tests that do `from app import app`.
app = create_app()
