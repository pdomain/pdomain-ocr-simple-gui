from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app
from pdomain_ocr_simple_gui.routes import model_cache


def _clear_hf_cache_env(monkeypatch) -> None:
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)


def test_get_model_cache_status_reports_uncached_paths(monkeypatch, tmp_path: Path) -> None:
    _clear_hf_cache_env(monkeypatch)
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setattr(model_cache, "_try_cached_path", lambda filename: None)

    client = TestClient(create_app())
    resp = client.get("/api/models/cache")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "repo": "pdomain/pdomain-ocr-models",
        "cache_root": str(tmp_path / "hf" / "hub"),
        "cached": False,
        "files": [
            {
                "filename": "detection/pdomain-all-detection-model-finetuned.pt",
                "cached": False,
                "path": None,
            },
            {
                "filename": "recognition/pdomain-all-recognition-model-finetuned.pt",
                "cached": False,
                "path": None,
            },
        ],
    }


def test_get_model_cache_status_expands_hf_hub_cache(monkeypatch, tmp_path: Path) -> None:
    _clear_hf_cache_env(monkeypatch)
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HF_HUB_CACHE", "~/hf-hub")
    monkeypatch.setattr(model_cache, "_try_cached_path", lambda filename: None)

    client = TestClient(create_app())
    resp = client.get("/api/models/cache")

    assert resp.status_code == 200
    assert resp.json()["cache_root"] == str(tmp_path / "home" / "hf-hub")


def test_get_model_cache_status_honors_legacy_huggingface_hub_cache(monkeypatch, tmp_path: Path) -> None:
    _clear_hf_cache_env(monkeypatch)
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path / "legacy-hub"))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))
    monkeypatch.setattr(model_cache, "_try_cached_path", lambda filename: None)

    client = TestClient(create_app())
    resp = client.get("/api/models/cache")

    assert resp.status_code == 200
    assert resp.json()["cache_root"] == str(tmp_path / "legacy-hub")


def test_get_model_cache_status_expands_hf_home(monkeypatch, tmp_path: Path) -> None:
    _clear_hf_cache_env(monkeypatch)
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HF_HOME", "~/hf")
    monkeypatch.setattr(model_cache, "_try_cached_path", lambda filename: None)

    client = TestClient(create_app())
    resp = client.get("/api/models/cache")

    assert resp.status_code == 200
    assert resp.json()["cache_root"] == str(tmp_path / "home" / "hf" / "hub")


def test_post_precache_downloads_and_returns_paths(monkeypatch, tmp_path: Path) -> None:
    _clear_hf_cache_env(monkeypatch)
    monkeypatch.delenv("PDOMAIN_API_TOKEN", raising=False)
    det = tmp_path / "det.pt"
    reco = tmp_path / "reco.pt"
    det.write_bytes(b"det")
    reco.write_bytes(b"reco")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setattr(model_cache, "resolve_ocr_models", lambda: (det, reco))

    client = TestClient(create_app())
    resp = client.post("/api/models/precache")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "repo": "pdomain/pdomain-ocr-models",
        "cache_root": str(tmp_path / "hf" / "hub"),
        "cached": True,
        "files": [
            {
                "filename": "detection/pdomain-all-detection-model-finetuned.pt",
                "cached": True,
                "path": str(det),
            },
            {
                "filename": "recognition/pdomain-all-recognition-model-finetuned.pt",
                "cached": True,
                "path": str(reco),
            },
        ],
    }
