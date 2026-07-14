"""FastAPI application for pdomain-ocr-simple-gui."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from pdomain_ocr_simple_gui.constants import APP_ID

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pdomain_ops.gpu.local_stage import LocalStageDispatcher
    from pdomain_ops.suite.prefs import PrefsAdapter
    from pdomain_ops.suite.types import CommonUIPrefs, InstalledApp, UIPrefs

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


class _SharedPrefsAdapter:
    """``PrefsAdapter`` that prefers the lifespan-managed singleton.

    The suite mount (``mount_routes()``) is wired synchronously inside
    ``create_app()``, which runs *before* FastAPI's lifespan — and therefore
    before module-level ``_prefs_adapter`` is set. This proxy lets suite
    routes share the exact same ``LocalFilePrefs`` instance as ``/api/prefs``
    once lifespan has started (so a mocked/patched ``_prefs_adapter`` is
    visible to suite routes too), while still working for callers that build
    the app without ever running lifespan (e.g. a bare
    ``TestClient(create_app())``): a fallback adapter is constructed lazily,
    on first actual use, so it resolves env-var-driven paths (e.g.
    ``PD_SUITE_DATA_DIR``) as of *call* time rather than at mount time.
    """

    def __init__(self) -> None:
        self._fallback: PrefsAdapter | None = None

    def _resolve(self) -> PrefsAdapter:
        adapter = get_prefs_adapter()
        if adapter is not None:
            return adapter
        if self._fallback is None:
            from pdomain_ops.suite.prefs import LocalFilePrefs

            self._fallback = LocalFilePrefs()
        return self._fallback

    def read(self) -> UIPrefs:
        """Delegate to the resolved adapter's ``read()``."""
        return self._resolve().read()

    def write_common(self, common: CommonUIPrefs) -> None:
        """Delegate to the resolved adapter's ``write_common()``."""
        self._resolve().write_common(common)

    def write_app(self, app_id: str, payload: dict[str, object]) -> None:
        """Delegate to the resolved adapter's ``write_app()``.

        ``dict[str, object]`` here is narrower than upstream
        ``PrefsAdapter.write_app``'s ``dict[str, Any]`` (pdomain_ops.suite.prefs)
        — this proxy never inspects ``payload``, only forwards it, so the
        narrower value type is both accurate and accepted at the delegation
        call site.
        """
        self._resolve().write_app(app_id, payload)


def _migrate_unknown_app_prefs(prefs_adapter: PrefsAdapter, app_id: str) -> None:
    """One-time migration: recover a compute-device pref stranded under "unknown".

    Before this fix, ``mount_routes()`` was called with no ``suite_app``, so
    ``mount_device_routes()`` defaulted to ``app_id="unknown"`` — any
    compute-device preference a user set via Settings persisted under
    ``apps["unknown"]`` instead of ``apps[app_id]``. Copy it over so existing
    installs don't silently lose the setting.

    ``PrefsAdapter`` (pdomain_ops.suite.prefs) exposes no delete primitive —
    only ``read``/``write_common``/``write_app`` — so the stray
    ``compute_device`` key is cleared from the "unknown" section rather than
    the section being removed outright; an app section with no
    ``compute_device`` is otherwise inert.
    """
    snapshot = prefs_adapter.read()
    unknown_section = snapshot.apps.get("unknown")
    if not unknown_section:
        return
    stray_device = unknown_section.get("compute_device")
    if not stray_device:
        return
    real_section = dict(snapshot.apps.get(app_id) or {})
    if real_section.get("compute_device"):
        return  # real app key already has an explicit device — don't clobber it
    real_section["compute_device"] = stray_device
    prefs_adapter.write_app(app_id, real_section)
    cleared_unknown = dict(unknown_section)
    del cleared_unknown["compute_device"]
    prefs_adapter.write_app("unknown", cleared_unknown)


def _build_suite_app() -> InstalledApp:
    """Build the ``InstalledApp`` descriptor this process registers under.

    Reads the bundled ``pdomain-suite.json`` fragment (the same source
    ``__main__.py``'s desktop-shortcut/suite-registry flows use) and fills in
    the two runtime-only fields, ``binary`` and ``version``. Used solely so
    ``mount_routes()`` mounts device/update routes under our real
    ``app_id`` ("pdomain-ocr-simple-gui") instead of the "unknown" default.
    """
    from pdomain_ops.suite.types import InstalledApp

    pkg = "pdomain_ocr_simple_gui"
    raw = (importlib.resources.files(pkg) / "pdomain-suite.json").read_text(encoding="utf-8")
    fragment = cast("dict[str, object]", json.loads(raw))
    try:
        version = importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        version = "0.0.0"
    return InstalledApp.model_validate({**fragment, "binary": sys.executable, "version": version})


def _resolve_device() -> str:
    """Return the effective compute device, resolved fresh on every call.

    Passed as ``LocalStageDispatcher(device_resolver=...)`` — the dispatcher
    calls this once per stage dispatch rather than once at construction, so a
    compute-device preference change in Settings takes effect on the next OCR
    run without restarting the process. Reads the module-level
    ``_prefs_adapter`` (not a snapshot captured at definition time) so it
    reflects whatever lifespan most recently wired in.

    Falls back to ``pick_device()`` directly when the prefs adapter failed to
    initialise, matching ``resolve_effective_device``'s own behaviour when no
    preference is persisted.
    """
    from pdomain_ops.gpu.device import pick_device
    from pdomain_ops.suite.device_prefs import resolve_effective_device

    if _prefs_adapter is None:
        return pick_device()
    return resolve_effective_device(_prefs_adapter, APP_ID)


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

        # LocalFilePrefs acquires its file lock with a finite timeout (DEFAULT_LOCK_TIMEOUT
        # = 5s as of pdomain-ops v0.10.0). On timeout it raises PrefsLockTimeout instead
        # of blocking forever. Route handlers catch PrefsLockTimeout and degrade gracefully
        # (GET → defaults, PUT → log + return merged payload). See routes/prefs.py.
        _prefs_adapter = LocalFilePrefs()
    except Exception:  # optional prefs integration — app runs without it
        logger.exception(
            "Failed to initialise prefs adapter; running without prefs",
            extra={"context": "LocalFilePrefs()"},
        )
        _prefs_adapter = None

    if _prefs_adapter is not None:
        try:
            _migrate_unknown_app_prefs(_prefs_adapter, APP_ID)
        except Exception:  # one-time migration is best-effort — never block startup
            logger.exception(
                "Failed to migrate stray 'unknown' app prefs to the real app_id",
                extra={"context": "_migrate_unknown_app_prefs", "app_id": APP_ID},
            )

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

            _dispatcher = LocalStageDispatcher(device_resolver=_resolve_device)
            register_default_stages(_dispatcher)
        except Exception:  # default stages optional — fall back to bare dispatcher
            logger.exception(
                "register_default_stages() failed; falling back to bare LocalStageDispatcher",
                extra={"context": "register_default_stages(_dispatcher)"},
            )
            from pdomain_ops.gpu import LocalStageDispatcher

            _dispatcher = LocalStageDispatcher(device_resolver=_resolve_device)
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
    from pdomain_ocr_simple_gui.routes.model_cache import router as model_cache_router
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
    _app.include_router(model_cache_router)

    # Mount suite plumbing routes (/api/suite/*, /api/icons/*, /healthz).
    # adapters.prefs is a proxy that shares state with the app's own
    # _prefs_adapter (once lifespan has started) and suite_app carries our
    # real app_id — mounting with neither (the pre-fix behaviour) made
    # mount_device_routes() default to app_id="unknown", so every
    # compute-device preference silently landed in the wrong prefs section.
    try:
        from pdomain_ops.suite.routes import (
            mount_routes as _mount_suite_routes,
        )
        from pdomain_ops.suite.types import SuiteAdapters

        adapters = SuiteAdapters.local()
        adapters.prefs = _SharedPrefsAdapter()
        suite_app = _build_suite_app()
        _mount_suite_routes(_app, adapters, suite_app=suite_app)
    except Exception:  # suite plumbing routes optional — app serves without them
        logger.exception(
            "Failed to mount suite plumbing routes; /api/suite/* will be unavailable",
            extra={"context": "mount_routes(_app, adapters, suite_app=suite_app)"},
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
