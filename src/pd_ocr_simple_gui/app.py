"""FastAPI application for pd-ocr-simple-gui."""

from __future__ import annotations

import importlib.resources
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pd_ocr_ops.gpu.local_stage import LocalStageDispatcher  # pyright: ignore[reportMissingTypeStubs]
    from pd_ocr_ops.suite.prefs import PrefsAdapter  # pyright: ignore[reportMissingTypeStubs]

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
    try:
        from pd_ocr_ops.suite.prefs import LocalFilePrefs  # pyright: ignore[reportMissingTypeStubs]

        _prefs_adapter = LocalFilePrefs()
    except Exception:  # noqa: BLE001  # optional prefs integration — app runs without it
        _prefs_adapter = None
    try:
        from pd_ocr_ops.gpu import (  # pyright: ignore[reportMissingTypeStubs]
            LocalStageDispatcher,
            register_default_stages,
        )

        _dispatcher = LocalStageDispatcher()
        register_default_stages(_dispatcher)
    except Exception:  # noqa: BLE001  # default stages optional — fall back to bare dispatcher
        from pd_ocr_ops.gpu import LocalStageDispatcher  # pyright: ignore[reportMissingTypeStubs]

        _dispatcher = LocalStageDispatcher()
    # Register this app with the suite registry (best-effort — never crash on failure)
    try:
        from pd_ocr_ops.suite import register_self  # pyright: ignore[reportMissingTypeStubs]

        register_self(_caller_package="pd_ocr_simple_gui")
    except Exception:  # noqa: BLE001, S110  # suite self-registration is best-effort — never crash startup
        pass
    yield
    _prefs_adapter = None
    _dispatcher = None


app = FastAPI(
    title="pd-ocr-simple-gui",
    description="Drag-and-drop OCR app",
    version="0.1.0a0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes.
# E402 suppressed below: routers are imported after `app` is defined to avoid
# a circular import (the route modules import `app` helpers).
from pd_ocr_simple_gui.routes.jobs import router as jobs_router  # noqa: E402
from pd_ocr_simple_gui.routes.pages import router as pages_router  # noqa: E402
from pd_ocr_simple_gui.routes.prefs import router as prefs_router  # noqa: E402

app.include_router(jobs_router)
app.include_router(pages_router)
app.include_router(prefs_router)

# Mount suite plumbing routes (/api/suite/*, /api/icons/*, /healthz)
try:
    from pd_ocr_ops.suite.routes import (  # pyright: ignore[reportMissingTypeStubs]
        mount_routes as _mount_suite_routes,
    )

    _mount_suite_routes(app)
except Exception:  # noqa: BLE001, S110  # suite plumbing routes optional — app serves without them
    pass


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


_FRONTEND_DIR = Path(__file__).parent / "frontend"

_ALLOWED_SELF_ICON_SIZES = {16, 24, 32, 48, 64, 128, 256}


@app.get("/api/self/icons/{size}")
async def get_self_icon(size: int) -> Response:
    """Serve this app's own icon for the given size (PNG)."""
    if size not in _ALLOWED_SELF_ICON_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported size {size}. Allowed: {sorted(_ALLOWED_SELF_ICON_SIZES)}",
        )
    icons_pkg = importlib.resources.files("pd_ocr_simple_gui") / "icons"
    icon_file = icons_pkg / f"{size}.png"
    try:
        # importlib.resources Traversable has .read_bytes() at runtime; not in the stub protocol
        icon_bytes = icon_file.read_bytes()  # type: ignore[attr-defined]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Icon {size}.png not found") from exc
    return Response(content=icon_bytes, media_type="image/png")


# Serve static JS/CSS assets — must come before the catch-all route.
# check_dir=False skips the existence check at startup; missing-assets requests 404 naturally.
app.mount(
    "/assets",
    StaticFiles(directory=_FRONTEND_DIR / "assets", check_dir=False),
    name="assets",
)


# SPA catch-all — React Router owns all non-API paths.
# MUST be registered last so it never shadows /api/* routes.
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    """Serve the React SPA index.html for any unmatched path."""
    _ = full_path
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend not built — run make frontend-build",
        )
    return FileResponse(index)
