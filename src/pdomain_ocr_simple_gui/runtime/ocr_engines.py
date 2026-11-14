"""Runtime OCR engine capability detection."""

from __future__ import annotations

import functools
import importlib
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


@functools.cache
def detect_doctr() -> OcrEngineStatus:
    """Report whether DocTR can run, by importing PyTorch once.

    On Windows without the Visual C++ runtime, importing torch raises
    OSError (WinError 126 loading c10.dll). The app used to report DocTR as
    available and then fail every page with an unrelated message. The result
    is cached: a failed torch import cannot be retried in the same process.
    """
    try:
        _import_torch()
    except ImportError as exc:
        reason = f"PyTorch is not installed: {exc}"
    except OSError as exc:
        if sys.platform == "win32":
            reason = (
                f"PyTorch could not load its libraries ({exc}). Install the Microsoft "
                f"Visual C++ Redistributable (x64) from {VC_REDIST_URL}, then restart this app."
            )
        else:
            reason = f"PyTorch could not load its libraries: {exc}"
    else:
        return OcrEngineStatus(id="doctr", label="DocTR", available=True)
    return OcrEngineStatus(id="doctr", label="DocTR", available=False, reason=reason)


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
