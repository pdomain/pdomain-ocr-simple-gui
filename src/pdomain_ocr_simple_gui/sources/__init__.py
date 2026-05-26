from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class SourceError(Exception):
    """Base class for Source materialization failures."""


class SourceNotFound(SourceError):  # noqa: N818
    """The configured source does not exist."""


class SourceInvalid(SourceError):  # noqa: N818
    """The source exists but is not usable (wrong type, unreadable)."""


class SourceTooLarge(SourceError):  # noqa: N818
    """The source exceeds configured size or count limits."""


@runtime_checkable
class Source(Protocol):
    def materialize(self) -> Path: ...
