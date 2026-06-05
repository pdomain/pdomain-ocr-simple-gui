"""Tests for --update CLI flag."""


def test_update_flag_invokes_apply(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "pdomain_ocr_simple_gui.__main__.apply_upgrade",
        lambda dist, **k: seen.setdefault("dist", dist),
    )
    from pdomain_ocr_simple_gui.__main__ import main

    main(["--update"])
    assert seen["dist"] == "pdomain-ocr-simple-gui"


def test_update_flag_parses():
    from pdomain_ocr_simple_gui.__main__ import _parse_args

    args = _parse_args(["--update"])
    assert args.update is True


def test_update_flag_defaults_false():
    from pdomain_ocr_simple_gui.__main__ import _parse_args

    args = _parse_args([])
    assert args.update is False
