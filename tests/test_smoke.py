"""Smoke test — verifies the package can be imported."""

import pd_ocr_simple_gui


def test_import() -> None:
    """Package imports without error."""
    assert pd_ocr_simple_gui is not None
