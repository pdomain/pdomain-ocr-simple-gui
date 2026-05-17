"""FastAPI application for pd-ocr-simple-gui."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pd_ocr_ops.gpu.local_stage import LocalStageDispatcher
    from pd_ocr_ops.suite.prefs import PrefsAdapter

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
    """Wire prefs adapter and stage dispatcher at startup."""
    global _prefs_adapter, _dispatcher  # noqa: PLW0603
    try:
        from pd_ocr_ops.suite.prefs import LocalFilePrefs

        _prefs_adapter = LocalFilePrefs()
    except Exception:  # noqa: BLE001
        _prefs_adapter = None
    try:
        from pd_ocr_ops.gpu import LocalStageDispatcher, register_default_stages

        _dispatcher = LocalStageDispatcher()
        register_default_stages(_dispatcher)
    except Exception:  # noqa: BLE001
        from pd_ocr_ops.gpu import LocalStageDispatcher

        _dispatcher = LocalStageDispatcher()
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

# Register routes
from pd_ocr_simple_gui.routes.jobs import router as jobs_router  # noqa: E402
from pd_ocr_simple_gui.routes.pages import router as pages_router  # noqa: E402
from pd_ocr_simple_gui.routes.prefs import router as prefs_router  # noqa: E402

app.include_router(jobs_router)
app.include_router(pages_router)
app.include_router(prefs_router)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "ok"}
