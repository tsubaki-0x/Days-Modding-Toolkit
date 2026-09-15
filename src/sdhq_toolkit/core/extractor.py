from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from ..formats.gpk.reader import GPKReader


def unpack_archive(
    archive: Path,
    workspace: Path,
    key: bytes,
    *,
    progress: Callable[[int, int, str, int], None] | None = None,
    paths=None,
    cancel=None,
) -> tuple[Path, dict]:
    destination = workspace / archive.stem
    if paths is not None or (destination / ".sdhq" / "archive.json").is_file():
        from .partial import extract_selection
        metadata = extract_selection(archive, destination, key, paths, progress=progress, cancel=cancel)
    else:
        metadata = GPKReader(archive, key).extract(destination, progress=progress, cancel=cancel)
    return destination, metadata
