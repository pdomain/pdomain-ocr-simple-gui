"""Validate future cache settings without overwriting user files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pdomain_ocr_simple_gui.routes.prefs import _validate_jobs_location

if TYPE_CHECKING:
    from pathlib import Path

    from httpx import AsyncClient


def test_writability_probe_preserves_existing_named_file(tmp_path: Path) -> None:
    sentinel = tmp_path / ".pd-ocr-write-probe"
    _ = sentinel.write_text("user data", encoding="utf-8")
    _validate_jobs_location(str(tmp_path))
    assert sentinel.read_text(encoding="utf-8") == "user data"


async def test_model_cache_preference_requires_absolute_path(client_with_mock_prefs: AsyncClient) -> None:
    response = await client_with_mock_prefs.put("/api/prefs", json={"model_cache_location": "relative"})
    assert response.status_code == 400


async def test_new_model_root_inside_runtime_is_rejected_before_any_folder_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client_with_mock_prefs: AsyncClient
) -> None:
    import sys
    from unittest.mock import MagicMock

    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(sys, "prefix", str(runtime))
    valid_jobs = tmp_path / "new-jobs"
    invalid_model = runtime / "models"
    adapter = get_prefs_adapter()
    assert adapter is not None
    saved = MagicMock()
    monkeypatch.setattr(adapter, "write_app", saved)
    response = await client_with_mock_prefs.put(
        "/api/prefs", json={"jobs_location": str(valid_jobs), "model_cache_location": str(invalid_model)}
    )
    assert response.status_code == 400
    assert "outside" in response.json()["detail"]
    assert not valid_jobs.exists()
    assert not invalid_model.exists()
    saved.assert_not_called()


@pytest.mark.parametrize("provider", ["doctr", "huggingface/hub", "torch/hub"])
async def test_new_model_provider_symlink_into_runtime_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client_with_mock_prefs: AsyncClient, provider: str
) -> None:
    import sys
    from unittest.mock import MagicMock

    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(sys, "prefix", str(runtime))
    models = tmp_path / "models"
    link = models / provider
    link.parent.mkdir(parents=True)
    link.symlink_to(runtime, target_is_directory=True)
    adapter = get_prefs_adapter()
    assert adapter is not None
    saved = MagicMock()
    monkeypatch.setattr(adapter, "write_app", saved)
    response = await client_with_mock_prefs.put("/api/prefs", json={"model_cache_location": str(models)})
    assert response.status_code == 400
    assert "outside" in response.json()["detail"]
    assert sorted(runtime.iterdir()) == []
    saved.assert_not_called()


@pytest.mark.parametrize("field", ["jobs_location", "model_cache_location"])
async def test_malformed_new_storage_choice_returns_400_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client_with_mock_prefs: AsyncClient, field: str
) -> None:
    from unittest.mock import MagicMock

    from pdomain_ocr_simple_gui.app import get_prefs_adapter

    adapter = get_prefs_adapter()
    assert adapter is not None
    saved = MagicMock()
    monkeypatch.setattr(adapter, "write_app", saved)
    safe_jobs = tmp_path / "not-created-on-failure"
    response = await client_with_mock_prefs.put(
        "/api/prefs", json={"jobs_location": str(safe_jobs), field: str(tmp_path / "bad\0data")}
    )
    assert response.status_code == 400
    assert "resolve" in response.json()["detail"]
    assert not safe_jobs.exists()
    saved.assert_not_called()
