"""Tests for --install-desktop-shortcut and --remove-desktop-shortcut CLI flags.

Note: --desktop was removed in the browser-only pivot. These tests cover the
desktop shortcut management flags which remain valid for the browser-based app.
"""

from pdomain_ocr_simple_gui.__main__ import _parse_args


def test_install_shortcut_flag_parses():
    """--install-desktop-shortcut parses without error."""
    args = _parse_args(["--install-desktop-shortcut"])
    assert args.install_desktop_shortcut is True


def test_remove_shortcut_flag_parses():
    """--remove-desktop-shortcut parses without error."""
    args = _parse_args(["--remove-desktop-shortcut"])
    assert args.remove_desktop_shortcut is True


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
