"""Tests for runtime OCR engine capability helpers."""

from pdomain_ocr_simple_gui.runtime import ocr_engines
from pdomain_ocr_simple_gui.runtime.ocr_engines import OcrEngineStatus


def test_tesseract_english_alias_en_resolves_to_eng_when_installed(monkeypatch) -> None:
    monkeypatch.setattr(
        ocr_engines,
        "detect_tesseract",
        lambda: OcrEngineStatus(
            id="tesseract",
            label="Tesseract",
            available=True,
            languages=("eng", "osd"),
        ),
    )

    assert ocr_engines.resolve_engine_language("tesseract", "en") == "eng"
    assert ocr_engines.is_engine_request_available("tesseract", "en") == (True, None)
