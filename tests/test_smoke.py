"""Smoke test — verifies the package can be imported."""

import pdomain_ocr_simple_gui


def test_import() -> None:
    """Package imports without error."""
    assert pdomain_ocr_simple_gui is not None
