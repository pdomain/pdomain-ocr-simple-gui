"""Apply requested model locations before provider imports on the next launch."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from pdomain_ocr_simple_gui.cache_configuration import apply_model_cache_location

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def restore_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DOCTR_CACHE_DIR", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "TORCH_HOME"):
        monkeypatch.setenv(name, os.environ.get(name, ""))


def test_model_location_changes_only_unset_provider_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DOCTR_CACHE_DIR", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "TORCH_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCTR_CACHE_DIR", str(tmp_path / "shared-doctr"))
    apply_model_cache_location(str(tmp_path / "models"))
    assert os.environ["DOCTR_CACHE_DIR"] == str(tmp_path / "shared-doctr")
    assert os.environ["HF_HUB_CACHE"] == str(tmp_path / "models" / "huggingface" / "hub")
    assert os.environ["TORCH_HOME"] == str(tmp_path / "models" / "torch")
    assert "HF_HOME" not in os.environ


def test_huggingface_home_override_keeps_its_cache_and_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "existing-hf"))
    apply_model_cache_location(str(tmp_path / "models"))
    assert "HF_HUB_CACHE" not in os.environ
    assert os.environ["HF_HOME"] == str(tmp_path / "existing-hf")


def test_blank_model_preference_preserves_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TORCH_HOME", "/unchanged")
    apply_model_cache_location("")
    assert os.environ["TORCH_HOME"] == "/unchanged"
