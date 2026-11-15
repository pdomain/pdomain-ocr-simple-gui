"""Reuse authenticated desktop servers without starting duplicate backends."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from pdomain_ocr_simple_gui import desktop
from pdomain_ocr_simple_gui.instance import InstanceReply, InstanceStore, new_instance_record

if TYPE_CHECKING:
    from pathlib import Path


def test_second_launch_reuses_visible_client_without_new_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    record = new_instance_record("http://127.0.0.1:8004")
    request = Mock(
        return_value=InstanceReply(
            app_id=record.app_id, instance_id=record.instance_id, challenge="ok", accepted=True
        )
    )
    browser = Mock()
    monkeypatch.setattr(desktop, "request_instance", request)
    monkeypatch.setattr(desktop.webbrowser, "open", browser)
    desktop.show_existing(record)
    request.assert_called_once_with(record, "show")
    browser.assert_not_called()


def test_unfocusable_tab_gets_one_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    record = new_instance_record("http://127.0.0.1:8004")
    request = Mock(
        return_value=InstanceReply(
            app_id=record.app_id, instance_id=record.instance_id, challenge="ok", accepted=False
        )
    )
    browser = Mock(return_value=True)
    monkeypatch.setattr(desktop, "request_instance", request)
    monkeypatch.setattr(desktop.webbrowser, "open", browser)
    desktop.show_existing(record)
    browser.assert_called_once_with(record.origin)


def test_failed_browser_open_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    record = new_instance_record("http://127.0.0.1:8004")
    monkeypatch.setattr(
        desktop,
        "request_instance",
        Mock(
            return_value=InstanceReply(
                app_id=record.app_id, instance_id=record.instance_id, challenge="ok", accepted=False
            )
        ),
    )
    monkeypatch.setattr(desktop.webbrowser, "open", Mock(return_value=False))
    with pytest.raises(RuntimeError, match="browser"):
        desktop.show_existing(record)


def test_active_owner_with_unreadable_record_cannot_be_replaced(tmp_path: Path) -> None:
    owner = InstanceStore(tmp_path / "state")
    contender = InstanceStore(tmp_path / "state")
    with owner.lifetime_lock, pytest.raises(RuntimeError, match="unresponsive"):
        _ = desktop.wait_for_instance(contender, timeout=0)
    assert not owner.record_path.exists()


def test_existing_instance_requires_authenticated_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    with store.startup_lock, store.lifetime_lock:
        store.publish(record)
        request = Mock(
            return_value=InstanceReply(
                app_id=record.app_id, instance_id=record.instance_id, challenge="ok", accepted=True
            )
        )
        monkeypatch.setattr(desktop, "request_instance", request)
        assert desktop.wait_for_instance(store, timeout=1) == record
        assert request.call_count == 1
        assert request.call_args.args == (record, "status")
        assert 0 < request.call_args.kwargs["timeout"] <= 1


def test_first_launcher_holds_both_locks_before_starting_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[bool] = []

    def serve(store: InstanceStore) -> None:
        observed.extend([store.startup_lock.is_locked, store.lifetime_lock.is_locked])

    monkeypatch.setattr(desktop, "serve_new_instance", serve)
    desktop.run_desktop(tmp_path / "state")
    assert observed == [True, True]
    assert not InstanceStore(tmp_path / "state").lifetime_lock.is_locked


def test_failed_startup_releases_locks_for_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_store: InstanceStore) -> None:
        raise RuntimeError("startup failed")

    monkeypatch.setattr(desktop, "serve_new_instance", fail)
    with pytest.raises(RuntimeError, match="startup failed"):
        desktop.run_desktop(tmp_path / "state")
    contender = InstanceStore(tmp_path / "state")
    with contender.startup_lock.acquire(timeout=0), contender.lifetime_lock.acquire(timeout=0):
        assert contender.lifetime_lock.is_locked


def test_graphical_error_keeps_message_as_data(monkeypatch: pytest.MonkeyPatch) -> None:
    message = 'bad path; $(touch /unwanted) "quoted"'
    runner = Mock()
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    monkeypatch.setattr(desktop.shutil, "which", lambda name: "/usr/bin/zenity" if name == "zenity" else None)
    monkeypatch.setattr(desktop.subprocess, "run", runner)
    desktop.show_launch_error(message)
    assert runner.call_args.args[0] == [
        "/usr/bin/zenity",
        "--error",
        "--title=OCR Simple GUI",
        f"--text={message}",
    ]
    assert "shell" not in runner.call_args.kwargs
    assert runner.call_args.kwargs["timeout"] == 120


def test_missing_graphical_dialog_never_runs_an_arbitrary_command(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Mock()
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    monkeypatch.setattr(desktop.shutil, "which", lambda _name: None)
    monkeypatch.setattr(desktop.subprocess, "run", runner)
    desktop.show_launch_error("Cannot start")
    runner.assert_not_called()


def test_uninstall_marker_blocks_new_launch_until_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    _ = (state / "uninstall-in-progress.json").write_text("incomplete", encoding="utf-8")
    server = Mock()
    monkeypatch.setattr(desktop, "serve_new_instance", server)
    with pytest.raises(RuntimeError, match="uninstall is incomplete"):
        desktop.run_desktop(state)
    server.assert_not_called()
