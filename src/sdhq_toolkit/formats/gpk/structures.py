from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GPKHeader:
    magic: bytes = b""
    version: int | None = None
    entry_count: int | None = None
    table_offset: int | None = None
    raw: bytes = b""


@dataclass(slots=True)
class GPKEntry:
    path: str
    offset: int
    stored_size: int
    unpacked_size: int | None = None
    flags: int | None = None
    raw_metadata: bytes = field(default=b"", repr=False)

