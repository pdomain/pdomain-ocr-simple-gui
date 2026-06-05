"""Tests for --desktop, --install-desktop-shortcut, --remove-desktop-shortcut CLI flags."""

from pdomain_ocr_simple_gui.__main__ import PREFERRED_PORT, _parse_args


def test_desktop_flag_parses():
    args = _parse_args(["--desktop"])
    assert args.desktop is True


def test_desktop_flag_defaults_false():
    args = _parse_args([])
    assert args.desktop is False


def test_desktop_calls_run_windowed(monkeypatch):
    called = {}

    def _fake_run_windowed(module, **k):
        called["module"] = module
        called["kwargs"] = k

    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.run_windowed",
        _fake_run_windowed,
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--desktop"])
    assert called["module"] == "pdomain_ocr_simple_gui.app:app"
    assert called["kwargs"].get("preferred_port") == PREFERRED_PORT


def test_desktop_forwards_custom_port(monkeypatch):
    """--port is forwarded as preferred_port to run_windowed."""
    called = {}

    def _fake_run_windowed(module, **k):
        called["module"] = module
        called["kwargs"] = k

    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.run_windowed",
        _fake_run_windowed,
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--desktop", "--port", "9000"])
    assert called["kwargs"].get("preferred_port") == 9000


def test_install_shortcut_calls_install(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.install_shortcut",
        lambda app: called.setdefault("app", app),
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--install-desktop-shortcut"])
    assert "app" in called


def test_remove_shortcut_calls_remove(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.remove_shortcut",
        lambda app: called.setdefault("app", app),
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--remove-desktop-shortcut"])
    assert "app" in called
