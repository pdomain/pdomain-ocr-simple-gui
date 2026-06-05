"""OCR model cache status and precache routes."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pdomain_book_tools.hf import (
    DEFAULT_DET_FILENAME,
    DEFAULT_HF_REPO,
    DEFAULT_RECO_FILENAME,
    resolve_ocr_models,
)
from pydantic import BaseModel

from pdomain_ocr_simple_gui.auth import require_token

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelCacheFile(BaseModel):
    """Cache status for a single model file."""

    filename: str
    cached: bool
    path: str | None = None


class ModelCacheStatus(BaseModel):
    """Cache status for the default OCR model files."""

    repo: str
    cache_root: str
    cached: bool
    files: list[ModelCacheFile]


def _hf_cache_root() -> Path:
    """Return the effective Hugging Face Hub cache root."""
    hub_cache = os.environ.get("HF_HUB_CACHE")
    if hub_cache:
        return _expanded_path(hub_cache)

    legacy_hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if legacy_hub_cache:
        return _expanded_path(legacy_hub_cache)

    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return _expanded_path(hf_home) / "hub"

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return _expanded_path(xdg_cache) / "huggingface" / "hub"

    return Path.home() / ".cache" / "huggingface" / "hub"


def _expanded_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def _try_cached_path(filename: str) -> Path | None:
    """Return a cached HF path without downloading, or None when absent."""
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None

    try:
        cached = try_to_load_from_cache(
            repo_id=DEFAULT_HF_REPO,
            filename=filename,
            cache_dir=_hf_cache_root(),
            revision=None,
        )
    except (OSError, ValueError):
        return None

    if cached is None:
        return None

    if isinstance(cached, str):
        return Path(cached)

    if isinstance(cached, os.PathLike):
        raw_path = cached.__fspath__()
        if isinstance(raw_path, str):
            return Path(raw_path)

    return None


def _status_for_paths(det_path: Path | None, reco_path: Path | None) -> ModelCacheStatus:
    files = [
        ModelCacheFile(
            filename=DEFAULT_DET_FILENAME,
            cached=det_path is not None and det_path.exists(),
            path=str(det_path) if det_path is not None else None,
        ),
        ModelCacheFile(
            filename=DEFAULT_RECO_FILENAME,
            cached=reco_path is not None and reco_path.exists(),
            path=str(reco_path) if reco_path is not None else None,
        ),
    ]

    return ModelCacheStatus(
        repo=DEFAULT_HF_REPO,
        cache_root=str(_hf_cache_root()),
        cached=all(file.cached for file in files),
        files=files,
    )


@router.get("/cache", response_model=ModelCacheStatus, dependencies=[Depends(require_token)])
def get_model_cache_status() -> ModelCacheStatus:
    """Return whether the default OCR checkpoints are cached."""
    return _status_for_paths(
        _try_cached_path(DEFAULT_DET_FILENAME),
        _try_cached_path(DEFAULT_RECO_FILENAME),
    )


@router.post("/precache", response_model=ModelCacheStatus, dependencies=[Depends(require_token)])
def precache_models() -> ModelCacheStatus:
    """Download/cache the default OCR checkpoints."""
    det_path, reco_path = resolve_ocr_models()
    return _status_for_paths(det_path, reco_path)
