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


def _doctr_with_import(
    monkeypatch, outcome: BaseException | None, platform: str = "win32", installed: bool = True
):
    def fake_import() -> None:
        if outcome is not None:
            raise outcome

    ocr_engines._load_torch_status.cache_clear()
    monkeypatch.setattr(ocr_engines, "_import_torch", fake_import)
    monkeypatch.setattr(ocr_engines, "_torch_is_installed", lambda: installed)
    monkeypatch.setattr(ocr_engines.sys, "platform", platform)
    try:
        return ocr_engines.detect_doctr()
    finally:
        ocr_engines._load_torch_status.cache_clear()


def test_doctr_available_when_torch_imports(monkeypatch) -> None:
    status = _doctr_with_import(monkeypatch, None)
    assert status.available is True
    assert status.reason is None


def test_doctr_unavailable_names_vc_runtime_when_torch_dlls_fail_on_windows(monkeypatch) -> None:
    """Windows 11 without the VC++ runtime: torch raises WinError 126 loading
    c10.dll. The GUI claimed DocTR was available and every page then failed
    with "PyTorch is not available in this environment"."""
    exc = OSError(126, "The specified module could not be found. Error loading c10.dll")
    status = _doctr_with_import(monkeypatch, exc)
    assert status.available is False
    assert status.reason is not None
    assert "Visual C++ Redistributable" in status.reason
    assert "https://aka.ms/vc14/vc_redist.x64.exe" in status.reason
    assert "restart" in status.reason


def test_doctr_unavailable_reports_load_error_elsewhere(monkeypatch) -> None:
    status = _doctr_with_import(monkeypatch, OSError("libc10.so: cannot open"), platform="linux")
    assert status.available is False
    assert status.reason is not None
    assert "libc10.so" in status.reason
    assert "Visual C++" not in status.reason


def test_doctr_unavailable_when_torch_missing(monkeypatch) -> None:
    status = _doctr_with_import(monkeypatch, ImportError("No module named 'torch'"), installed=False)
    assert status.available is False
    assert status.reason is not None
    assert "PyTorch is not installed" in status.reason


def test_doctr_job_request_rejected_with_reason_when_torch_cannot_load(monkeypatch) -> None:
    exc = OSError(126, "Error loading c10.dll")
    ocr_engines._load_torch_status.cache_clear()
    monkeypatch.setattr(ocr_engines, "_import_torch", lambda: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(ocr_engines, "_torch_is_installed", lambda: True)
    monkeypatch.setattr(ocr_engines.sys, "platform", "win32")
    try:
        ok, reason = ocr_engines.is_engine_request_available("doctr", "en")
        engines = {e["id"]: e for e in ocr_engines.detect_ocr_engines()}
    finally:
        ocr_engines._load_torch_status.cache_clear()
    assert ok is False
    assert reason is not None
    assert "Visual C++ Redistributable" in reason
    assert engines["doctr"]["available"] is False


def test_doctr_second_import_after_dll_failure_still_gets_vc_advice(monkeypatch) -> None:
    """Real Windows sequence: /api/config's device probe imports torch first
    and hits WinError 126; every later import raises this ImportError. It must
    not be reported as "not installed"."""
    exc = ImportError(
        "`torch` can only be initialized once per process, so this module cannot be imported again"
    )
    status = _doctr_with_import(monkeypatch, exc, installed=True)
    assert status.available is False
    assert status.reason is not None
    assert "not installed" not in status.reason
    assert "Visual C++ Redistributable" in status.reason


def test_doctr_unavailable_on_unexpected_torch_import_error(monkeypatch) -> None:
    """A broken install can raise RuntimeError; /api/config must not 500."""
    status = _doctr_with_import(monkeypatch, RuntimeError("numpy ABI mismatch"), platform="linux")
    assert status.available is False
    assert status.reason is not None
    assert "numpy ABI mismatch" in status.reason


def test_doctr_windows_non_dll_failure_gets_no_vc_advice(monkeypatch) -> None:
    status = _doctr_with_import(monkeypatch, ImportError("No module named 'typing_extensions'"))
    assert status.available is False
    assert status.reason is not None
    assert "Visual C++" not in status.reason


def test_doctr_not_installed_is_not_cached(monkeypatch) -> None:
    installed = {"value": False}
    ocr_engines._load_torch_status.cache_clear()
    monkeypatch.setattr(ocr_engines, "_torch_is_installed", lambda: installed["value"])
    monkeypatch.setattr(ocr_engines, "_import_torch", lambda: None)
    try:
        assert ocr_engines.detect_doctr().available is False
        installed["value"] = True
        assert ocr_engines.detect_doctr().available is True
    finally:
        ocr_engines._load_torch_status.cache_clear()
