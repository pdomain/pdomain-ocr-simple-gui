"""Runtime OCR engine capability detection."""

from __future__ import annotations

import functools
import importlib
import importlib.util
import sys
from dataclasses import dataclass
from typing import Literal

EngineId = Literal["doctr", "tesseract"]
TESSERACT_LANGUAGE_ALIASES = {
    "en": "eng",
}


@dataclass(frozen=True)
class OcrEngineStatus:
    """Runtime availability status for one OCR engine."""

    id: EngineId
    label: str
    available: bool
    reason: str | None = None
    languages: tuple[str, ...] = ()

    def as_config(self) -> dict[str, object]:
        """Return the frontend-facing config payload for this engine."""
        return {
            "id": self.id,
            "label": self.label,
            "available": self.available,
            "reason": self.reason,
        }


def detect_tesseract() -> OcrEngineStatus:
    """Return whether pytesseract can reach Tesseract and any language data."""
    try:
        import pytesseract  # pyright: ignore[reportMissingTypeStubs]  # pytesseract has no py.typed; no stubs available
        from pytesseract import TesseractError  # pyright: ignore[reportMissingTypeStubs]
    except ImportError:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason="Python package pytesseract is not installed.",
        )

    try:
        _ = pytesseract.get_tesseract_version()
    except (TesseractError, OSError) as exc:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason=f"Tesseract executable is unavailable: {exc}",
        )

    try:
        raw_langs: list[str] = list(pytesseract.get_languages(config=""))  # pyright: ignore[reportUnknownArgumentType]  # pytesseract untyped: get_languages return type is unknown
        languages = tuple(sorted(raw_langs))
    except (TesseractError, OSError) as exc:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason=f"Tesseract language data is unavailable: {exc}",
        )

    if not languages:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason="Tesseract language data is unavailable.",
        )

    return OcrEngineStatus(
        id="tesseract",
        label="Tesseract",
        available=True,
        languages=languages,
    )


VC_REDIST_URL = "https://aka.ms/vc14/vc_redist.x64.exe"


def _import_torch() -> None:
    _ = importlib.import_module("torch")


def _torch_is_installed() -> bool:
    return importlib.util.find_spec("torch") is not None


def _needs_vc_runtime(exc: BaseException) -> bool:
    """True when a torch import failure looks like missing Windows DLLs.

    WinError 126 is the error seen without the Visual C++ runtime. After a
    first failed import, torch raises "initialized once" for every later
    import in the process, which hides the original error.
    """
    text = str(exc)
    return (
        getattr(exc, "winerror", None) == 126
        or "DLL" in text
        or "c10.dll" in text
        or "initialized once" in text
    )


@functools.cache
def _load_torch_status() -> OcrEngineStatus:
    """Import torch once and cache the outcome.

    A failed load must be cached: torch cannot be imported again in the same
    process. Any exception counts, not only ImportError and OSError, so a
    broken install reports DocTR as unavailable instead of failing /api/config.
    """
    try:
        _import_torch()
    except Exception as exc:  # noqa: BLE001  # any torch import failure makes DocTR unavailable; the reason carries the detail
        if sys.platform == "win32" and _needs_vc_runtime(exc):
            reason = (
                "PyTorch is installed but could not load. Install the Microsoft Visual C++ "
                f"Redistributable (x64) from {VC_REDIST_URL}, then restart this app. "
                f"Detail: {exc}"
            )
        else:
            reason = f"PyTorch is installed but could not load: {exc}"
        return OcrEngineStatus(id="doctr", label="DocTR", available=False, reason=reason)
    return OcrEngineStatus(id="doctr", label="DocTR", available=True)


def detect_doctr() -> OcrEngineStatus:
    """Report whether DocTR can run.

    On Windows without the Visual C++ runtime, importing torch raises
    OSError (WinError 126 loading c10.dll). The app used to report DocTR as
    available and then fail every page with an unrelated message.

    "Not installed" is decided by whether torch can be found, and is not
    cached, so installing torch while the app runs is picked up.
    """
    if not _torch_is_installed():
        return OcrEngineStatus(
            id="doctr",
            label="DocTR",
            available=False,
            reason="PyTorch is not installed in this app's environment.",
        )
    return _load_torch_status()


def detect_ocr_engines() -> list[dict[str, object]]:
    """Return the OCR engines that the frontend can offer."""
    return [
        detect_doctr().as_config(),
        detect_tesseract().as_config(),
    ]


def resolve_engine_language(engine: EngineId, language: str) -> str:
    """Resolve app language aliases to the engine-specific language code."""
    normalized = language.strip()
    if engine == "tesseract":
        return TESSERACT_LANGUAGE_ALIASES.get(normalized.lower(), normalized)
    return normalized


def is_engine_request_available(engine: EngineId, language: str) -> tuple[bool, str | None]:
    """Validate the requested engine/language before queueing OCR work."""
    if engine == "doctr":
        doctr = detect_doctr()
        return doctr.available, doctr.reason

    resolved_language = resolve_engine_language(engine, language)
    status = detect_tesseract()
    if not status.available:
        return False, status.reason

    if resolved_language and resolved_language not in status.languages:
        available = ", ".join(status.languages)
        return (
            False,
            f"Tesseract language '{resolved_language}' is unavailable. Installed languages: {available}.",
        )

    return True, None
