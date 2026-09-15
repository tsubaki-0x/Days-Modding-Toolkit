from __future__ import annotations

from collections.abc import Callable
from typing import BinaryIO


DEFAULT_CHUNK_SIZE = 1024 * 1024
ChunkProgress = Callable[[int], None]


def copy_exact(
    source: BinaryIO,
    destination: BinaryIO,
    size: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress: ChunkProgress | None = None,
    cancel=None,
) -> int:
    """Copy exactly *size* bytes without loading the complete range in memory."""

    if size < 0:
        raise ValueError("Copy size cannot be negative")
    remaining = size
    copied = 0
    while remaining:
        if cancel:
            cancel.check()
        chunk = source.read(min(chunk_size, remaining))
        if not chunk:
            raise EOFError(f"Source ended with {remaining} byte(s) still expected")
        destination.write(chunk)
        copied += len(chunk)
        remaining -= len(chunk)
        if progress is not None:
            progress(copied)
    return copied
