"""Path containment checks that work on POSIX and Windows."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import PurePath


def is_strictly_within(candidate: PurePath, root: PurePath) -> bool:
    """Return True when *candidate* is inside *root* and is not *root* itself.

    Compare resolved paths. This compares path parts, so it accepts either
    separator and rejects a sibling such as ``rootx`` that merely shares a
    prefix with ``root``.
    """
    return candidate != root and candidate.is_relative_to(root)
