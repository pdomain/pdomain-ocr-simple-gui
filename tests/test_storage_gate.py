"""Keep storage migration exclusive through background request completion."""

from __future__ import annotations

import pytest

from pdomain_ocr_simple_gui.activity_gate import StorageBusyError, StorageGate


def test_active_work_blocks_migration_without_waiting() -> None:
    gate = StorageGate()
    with gate.activity(), pytest.raises(StorageBusyError, match="work"), gate.exclusive():
        pytest.fail("Migration started during work")
    with gate.exclusive():
        assert gate.migrating


def test_migration_blocks_new_work_and_cleans_up_after_failure() -> None:
    gate = StorageGate()
    with gate.exclusive(), pytest.raises(StorageBusyError, match="migration"), gate.activity():
        pytest.fail("Work started during migration")

    def fail() -> None:
        with gate.exclusive():
            raise OSError("copy failed")

    with pytest.raises(OSError):
        fail()
    assert not gate.migrating
    with gate.activity():
        assert gate.active_count == 1
    assert gate.active_count == 0
