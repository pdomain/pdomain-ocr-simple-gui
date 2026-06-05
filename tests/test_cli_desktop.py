"""Tests for --desktop, --install-desktop-shortcut, --remove-desktop-shortcut CLI flags."""

from pdomain_ocr_simple_gui.__main__ import _parse_args


def test_desktop_flag_parses():
    args = _parse_args(["--desktop"])
    assert args.desktop is True


def test_desktop_flag_defaults_false():
    args = _parse_args([])
    assert args.desktop is False


def test_desktop_calls_run_windowed(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.run_windowed",
        lambda module, **k: called.setdefault("module", module),
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--desktop"])
    assert called["module"] == "pdomain_ocr_simple_gui.app:app"


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
