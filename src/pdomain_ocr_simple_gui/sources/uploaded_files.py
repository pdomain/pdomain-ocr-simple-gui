# src/pdomain_ocr_simple_gui/sources/uploaded_files.py
"""Source implementation that resolves an upload_id to a staging directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from pdomain_ocr_simple_gui.sources import Source, SourceNotFound

if TYPE_CHECKING:
    from pathlib import Path


class UploadedFilesSource(Source):
    """Materializes an upload staging directory identified by upload_id.

    The upload route writes files to ``root/<id>`` (plain uuid hex).
    This resolver first checks ``root/upload-<id>`` (canonical prefix form),
    then falls back to ``root/<id>`` (the actual upload staging dir).
    """

    _upload_id: str
    _root: Path

    def __init__(self, upload_id: str, root: Path) -> None:
        """Initialise with an upload_id and the staging root directory."""
        self._upload_id = upload_id
        self._root = root

    @override
    def materialize(self) -> Path:
        """Return the staging directory for this upload_id.

        Raises SourceNotFound if neither form of the directory exists.
        """
        target = self._root / f"upload-{self._upload_id}"
        if target.is_dir():
            return target
        # also accept root/<id> (the upload route writes here)
        alt = self._root / self._upload_id
        if alt.is_dir():
            return alt
        raise SourceNotFound(str(target))
