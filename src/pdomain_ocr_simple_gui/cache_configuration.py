"""Apply saved model cache choices before loading OCR providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CacheStartupState:
    """Remember the cache choice applied at process startup."""

    location: str = ""


startup_state = CacheStartupState()


def apply_model_cache_location(location: str) -> None:
    """Set unset provider cache paths without moving shared caches or credentials."""
    startup_state.location = location
    if not location:
        return
    root = Path(location).expanduser()
    if not os.environ.get("DOCTR_CACHE_DIR"):
        os.environ["DOCTR_CACHE_DIR"] = str(root / "doctr")
    if not any(os.environ.get(name) for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME")):
        os.environ["HF_HUB_CACHE"] = str(root / "huggingface" / "hub")
    if not os.environ.get("TORCH_HOME"):
        os.environ["TORCH_HOME"] = str(root / "torch")


def apply_saved_model_cache_location() -> None:
    """Load the app preference before importing any model provider."""
    from pdomain_ops.suite.prefs import LocalFilePrefs

    from pdomain_ocr_simple_gui.app_preferences import AppPreferencesStore
    from pdomain_ocr_simple_gui.constants import APP_ID
    from pdomain_ocr_simple_gui.locations import get_locations

    legacy: dict[str, object] = dict(LocalFilePrefs().read().apps.get(APP_ID, {}))
    prefs = AppPreferencesStore(get_locations().preferences_path).read_app(legacy)
    location = prefs.get("model_cache_location", "")
    apply_model_cache_location(location if isinstance(location, str) else "")


def effective_model_paths() -> dict[str, str]:
    """Report provider locations without importing providers or changing caches."""
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    hf_home = Path(os.environ.get("HF_HOME", cache / "huggingface"))
    hf_hub = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE") or str(hf_home / "hub")
    return {
        "doctr": str(Path(os.environ.get("DOCTR_CACHE_DIR", Path.home() / ".cache" / "doctr")).expanduser()),
        "huggingface": str(Path(hf_hub).expanduser()),
        "torch": str(Path(os.environ.get("TORCH_HOME", cache / "torch")).expanduser() / "hub"),
    }
