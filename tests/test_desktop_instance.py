"""Verify private, authenticated discovery of desktop instances."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from pdomain_ocr_simple_gui.instance import InstanceRecord, InstanceStore, new_instance_record

if TYPE_CHECKING:
    from pathlib import Path


def test_record_round_trip_keeps_secret_out_of_representation(tmp_path: Path) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    assert record.capability.get_secret_value() not in repr(record)
    with store.startup_lock, store.lifetime_lock:
        store.publish(record)
        assert store.read() == record
    assert record.capability.get_secret_value() in store.record_path.read_text()
    if os.name != "nt":
        assert store.record_path.stat().st_mode & 0o777 == 0o600


def test_publish_requires_both_os_locks(tmp_path: Path) -> None:
    store = InstanceStore(tmp_path / "state")
    record = new_instance_record("http://127.0.0.1:8004")
    with pytest.raises(RuntimeError, match="locks"):
        store.publish(record)
    with store.startup_lock, pytest.raises(RuntimeError, match="locks"):
        store.publish(record)
    assert not store.record_path.exists()


def test_independent_store_cannot_take_held_lifetime_lock(tmp_path: Path) -> None:
    first = InstanceStore(tmp_path / "state")
    second = InstanceStore(tmp_path / "state")
    with first.lifetime_lock, pytest.raises(TimeoutError):
        _ = second.lifetime_lock.acquire(timeout=0)


def test_cleanup_never_removes_another_instance_record(tmp_path: Path) -> None:
    store = InstanceStore(tmp_path / "state")
    original = new_instance_record("http://127.0.0.1:8004")
    replacement = new_instance_record("http://127.0.0.1:8005")
    with store.startup_lock, store.lifetime_lock:
        store.publish(replacement)
        assert not store.remove_owned(original)
        assert store.read() == replacement
        assert store.remove_owned(replacement)
        assert store.read() is None


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://0.0.0.0:8004",
        "http://127.0.0.1:8004/path",
        "http://user@127.0.0.1:8004",
        "http://127.0.0.1:8004?token=secret",
        "http://localhost:8004",
        "http://127.0.0.1:0",
        "https://127.0.0.1:8004",
    ],
)
def test_record_rejects_unsafe_origins(origin: str) -> None:
    with pytest.raises(ValueError):
        _ = new_instance_record(origin)


def test_ipv6_loopback_is_supported() -> None:
    assert new_instance_record("http://[::1]:8004").origin == "http://[::1]:8004"


def test_read_rejects_malformed_record_and_symlink(tmp_path: Path) -> None:
    store = InstanceStore(tmp_path / "state")
    with store.startup_lock:
        _ = store.record_path.write_text('{"pid":123}')
        with pytest.raises(ValueError):
            _ = store.read()
        store.record_path.unlink()
        target = tmp_path / "other.json"
        _ = target.write_text(new_instance_record("http://127.0.0.1:8004").private_json())
        store.record_path.symlink_to(target)
        with pytest.raises(ValueError, match="symlink"):
            _ = store.read()


def test_schema_and_app_identity_cannot_be_forged() -> None:
    record = new_instance_record("http://127.0.0.1:8004").private_json()
    record = record.replace("pdomain-ocr-simple-gui", "other-app")
    with pytest.raises(ValueError):
        _ = InstanceRecord.model_validate_json(record)
