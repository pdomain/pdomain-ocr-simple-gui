"""Security tests for SOURCE_ROOT_ALLOWLIST enforcement in LocalPathSource.

These tests verify that when SOURCE_ROOT_ALLOWLIST is configured,
LocalPathSource rejects paths outside the allowlist (including symlink escapes),
and that omitting the env var preserves unrestricted behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.sources.local_path import LocalPathSource

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_dir(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# allowlist-set tests
# ---------------------------------------------------------------------------


def test_source_path_within_allowlist_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A path inside an allowlisted root is accepted without error."""
    allowed = _make_dir(tmp_path, "allowed")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", str(allowed))

    target = _make_dir(allowed, "project")
    # Should not raise
    src = LocalPathSource(target)
    assert src.materialize() == target


def test_source_path_outside_allowlist_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A path outside every allowlisted root raises ValueError."""
    allowed = _make_dir(tmp_path, "allowed")
    outside = _make_dir(tmp_path, "outside")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", str(allowed))

    with pytest.raises(ValueError, match="not within any allowed source root"):
        LocalPathSource(outside)


def test_multiple_allowlist_roots_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A path inside any one of multiple colon-separated roots is accepted."""
    root_a = _make_dir(tmp_path, "root_a")
    root_b = _make_dir(tmp_path, "root_b")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", f"{root_a}:{root_b}")

    target = _make_dir(root_b, "project")
    # Should not raise
    LocalPathSource(target)


def test_symlink_escaping_allowlist_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A symlink inside the allowed dir that resolves outside is rejected."""
    allowed = _make_dir(tmp_path, "allowed")
    outside = _make_dir(tmp_path, "outside")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", str(allowed))

    # Create a symlink inside allowed/ that points to outside/
    link = allowed / "escape_link"
    link.symlink_to(outside)

    with pytest.raises(ValueError, match="not within any allowed source root"):
        LocalPathSource(link)


def test_allowlist_root_itself_not_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The allowlist root itself is not a valid source (must be a *strict* child)."""
    allowed = _make_dir(tmp_path, "allowed")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", str(allowed))

    with pytest.raises(ValueError, match="not within any allowed source root"):
        LocalPathSource(allowed)


# ---------------------------------------------------------------------------
# allowlist-unset / empty tests
# ---------------------------------------------------------------------------


def test_allowlist_not_set_accepts_any_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When SOURCE_ROOT_ALLOWLIST is absent, any path is accepted."""
    monkeypatch.delenv("SOURCE_ROOT_ALLOWLIST", raising=False)
    target = _make_dir(tmp_path, "anywhere")
    # Should not raise
    src = LocalPathSource(target)
    assert src.materialize() == target


def test_empty_allowlist_accepts_any_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When SOURCE_ROOT_ALLOWLIST is an empty string, any path is accepted."""
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", "")
    target = _make_dir(tmp_path, "anywhere")
    # Should not raise
    src = LocalPathSource(target)
    assert src.materialize() == target


def test_allowlist_whitespace_only_accepts_any_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When SOURCE_ROOT_ALLOWLIST is whitespace-only, treat as unset."""
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", "   ")
    target = _make_dir(tmp_path, "anywhere")
    # Should not raise
    LocalPathSource(target)


# ---------------------------------------------------------------------------
# env var format edge cases
# ---------------------------------------------------------------------------


def test_allowlist_with_trailing_colon_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trailing colon in allowlist (e.g. '/foo:') is tolerated (empty parts ignored)."""
    allowed = _make_dir(tmp_path, "allowed")
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", f"{allowed}:")

    target = _make_dir(allowed, "project")
    LocalPathSource(target)


def test_allowlist_nonexistent_root_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-existent root in the allowlist is silently skipped during matching."""
    allowed = _make_dir(tmp_path, "allowed")
    ghost = tmp_path / "ghost_does_not_exist"
    monkeypatch.setenv("SOURCE_ROOT_ALLOWLIST", f"{ghost}:{allowed}")

    target = _make_dir(allowed, "project")
    LocalPathSource(target)
