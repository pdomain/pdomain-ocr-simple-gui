"""Tests for GET /api/pages/{job_id}/{idx}/words."""

from fastapi.testclient import TestClient

from pd_ocr_simple_gui.app import create_app


def test_words_payload_shape(monkeypatch) -> None:
    """Happy-path: monkeypatched load_page_words returns word list."""
    fake = [{"text": "Hello", "bbox": {"x": 10, "y": 20, "w": 50, "h": 12}, "confidence": 0.95}]
    monkeypatch.setattr(
        "pd_ocr_simple_gui.routes.words.load_page_words",
        lambda job_id, idx: fake,
    )
    client = TestClient(create_app())
    resp = client.get("/api/pages/job-1/0/words")
    assert resp.status_code == 200
    assert resp.json() == {"words": fake}


def test_words_missing_returns_404(monkeypatch) -> None:
    """Missing page (load_page_words returns None) → 404."""
    monkeypatch.setattr(
        "pd_ocr_simple_gui.routes.words.load_page_words",
        lambda job_id, idx: None,
    )
    client = TestClient(create_app())
    resp = client.get("/api/pages/missing/0/words")
    assert resp.status_code == 404
