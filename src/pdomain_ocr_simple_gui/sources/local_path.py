from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from pdomain_ocr_simple_gui.sources import (
    Source,
    SourceInvalid,
    SourceNotFound,
    SourceTooLarge,
)

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".webp",
    # JPEG 2000 family — Pillow handles via OpenJPEG.
    ".jp2",
    ".j2k",
    ".jpf",
    ".jpx",
    ".jpm",
}
_MAX_UNCOMPRESSED_BYTES = 2 * 1024**3  # 2 GiB


def _get_allowlist() -> list[Path] | None:
    """Return the parsed SOURCE_ROOT_ALLOWLIST, or None when unset/empty."""
    raw = os.environ.get("SOURCE_ROOT_ALLOWLIST", "")
    if not raw.strip():
        return None
    roots: list[Path] = []
    for part in raw.split(":"):
        stripped = part.strip()
        if stripped:
            roots.append(Path(stripped))
    return roots if roots else None


def _check_allowlist(resolved: Path) -> None:
    """Raise ValueError if *resolved* is not a strict child of any allowed root.

    Does nothing when SOURCE_ROOT_ALLOWLIST is unset or empty.
    """
    roots = _get_allowlist()
    if roots is None:
        return
    resolved_str = str(resolved)
    for root in roots:
        try:
            root_resolved = root.resolve()
        except OSError:
            # Non-existent root — skip silently.
            continue
        root_str = str(root_resolved)
        # strict child: resolved must start with root/ and not equal root exactly
        if resolved_str.startswith(root_str + os.sep) and resolved_str != root_str:
            return
    raise ValueError(
        f"source path {resolved!r} is not within any allowed source root "
        f"(SOURCE_ROOT_ALLOWLIST={os.environ.get('SOURCE_ROOT_ALLOWLIST', '')!r})"
    )


class LocalPathSource(Source):
    """Source backed by a local filesystem path (folder, image, or zip)."""

    def __init__(self, path: Path, extract_root: Path | None = None) -> None:
        self._path = Path(path).expanduser()
        self._extract_root = extract_root
        # Allowlist check at accept time — resolve() follows symlinks, so a
        # symlink that escapes the allowed tree is caught here.
        _check_allowlist(self._path.resolve())

    def materialize(self) -> Path:
        """Return the materialized folder, creating a temp dir if needed."""
        if not self._path.exists():
            raise SourceNotFound(str(self._path))
        if self._path.is_dir():
            return self._path
        if self._path.suffix.lower() == ".zip":
            return self._extract_zip()
        if self._path.suffix.lower() in _IMAGE_EXTS:
            return self._wrap_single_image()
        raise SourceInvalid(f"{self._path} is not a folder, image, or .zip")

    def _wrap_single_image(self) -> Path:
        workdir = Path(
            tempfile.mkdtemp(
                prefix="pdomain-ocr-simple-gui-single-",
                dir=self._extract_root,
            )
        )
        shutil.copy2(self._path, workdir / self._path.name)
        return workdir

    def _extract_zip(self) -> Path:
        workdir = Path(
            tempfile.mkdtemp(
                prefix="pdomain-ocr-simple-gui-zip-",
                dir=self._extract_root,
            )
        )
        try:
            with zipfile.ZipFile(self._path) as zf:
                total = 0
                for info in zf.infolist():
                    # traversal guard
                    target = (workdir / info.filename).resolve()
                    if not str(target).startswith(str(workdir.resolve()) + "/"):
                        raise SourceInvalid(f"zip entry escapes extract root: {info.filename}")
                    total += info.file_size
                    if total > _MAX_UNCOMPRESSED_BYTES:
                        raise SourceTooLarge(f"zip exceeds {_MAX_UNCOMPRESSED_BYTES} uncompressed bytes")
                zf.extractall(workdir)
        except zipfile.BadZipFile as exc:
            raise SourceInvalid(f"not a valid zip: {self._path}") from exc
        return workdir
