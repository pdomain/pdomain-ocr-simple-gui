"""Tests for PDOMAIN_OCR_FAKE_DISPATCHER env-var seam in app.lifespan."""

from __future__ import annotations

import logging

import pytest

from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher


@pytest.mark.asyncio
async def test_fake_dispatcher_env_var_selects_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """When PDOMAIN_OCR_FAKE_DISPATCHER is set, get_dispatcher() returns FakeStageDispatcher.

    Re-runs the lifespan startup in-process with the env var set and asserts
    that the module-level _dispatcher is a FakeStageDispatcher instance.
    """
    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import lifespan

    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")

    from fastapi import FastAPI

    dummy_app = FastAPI()
    async with lifespan(dummy_app):
        dispatcher = app_mod.get_dispatcher()
        assert isinstance(dispatcher, FakeStageDispatcher), (
            f"Expected FakeStageDispatcher, got {type(dispatcher).__name__}"
        )


@pytest.mark.asyncio
async def test_fake_dispatcher_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When PDOMAIN_OCR_FAKE_DISPATCHER is set, a WARNING is emitted before startup.

    The warning must be visible at WARNING level so operators who accidentally
    set this env var in production cannot miss it.
    """
    from pdomain_ocr_simple_gui.app import lifespan

    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")

    from fastapi import FastAPI

    dummy_app = FastAPI()
    with caplog.at_level(logging.WARNING, logger="pdomain_ocr_simple_gui.app"):
        async with lifespan(dummy_app):
            pass

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("PDOMAIN_OCR_FAKE_DISPATCHER" in m for m in warning_messages), (
        "Expected a WARNING mentioning PDOMAIN_OCR_FAKE_DISPATCHER; "
        f"got warning messages: {warning_messages!r}"
    )


@pytest.mark.asyncio
async def test_fake_dispatcher_env_var_not_set_uses_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """When PDOMAIN_OCR_FAKE_DISPATCHER is unset, get_dispatcher() is NOT FakeStageDispatcher."""
    import pdomain_ocr_simple_gui.app as app_mod
    from pdomain_ocr_simple_gui.app import lifespan

    monkeypatch.delenv("PDOMAIN_OCR_FAKE_DISPATCHER", raising=False)

    from fastapi import FastAPI

    dummy_app = FastAPI()
    async with lifespan(dummy_app):
        dispatcher = app_mod.get_dispatcher()
        assert dispatcher is not None, "Dispatcher should be set after lifespan startup"
        assert not isinstance(dispatcher, FakeStageDispatcher), (
            "Expected a real dispatcher when env var is not set"
        )
