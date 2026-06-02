"""Runtime OCR engine capability detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EngineId = Literal["doctr", "tesseract"]


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
        import pytesseract
        from pytesseract import TesseractError
    except ImportError:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason="Python package pytesseract is not installed.",
        )

    try:
        pytesseract.get_tesseract_version()
    except (TesseractError, OSError) as exc:
        return OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=False,
            reason=f"Tesseract executable is unavailable: {exc}",
        )

    try:
        languages = tuple(sorted(pytesseract.get_languages(config="")))
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


def detect_ocr_engines() -> list[dict[str, object]]:
    """Return the OCR engines that the frontend can offer."""
    return [
        OcrEngineStatus(
            id="doctr",
            label="DocTR",
            available=True,
        ).as_config(),
        detect_tesseract().as_config(),
    ]


def is_engine_request_available(engine: EngineId, language: str) -> tuple[bool, str | None]:
    """Validate the requested engine/language before queueing OCR work."""
    if engine == "doctr":
        return True, None

    status = detect_tesseract()
    if not status.available:
        return False, status.reason

    if language and language not in status.languages:
        available = ", ".join(status.languages)
        return (
            False,
            f"Tesseract language '{language}' is unavailable. Installed languages: {available}.",
        )

    return True, None
