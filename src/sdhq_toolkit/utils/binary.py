from __future__ import annotations

from pathlib import Path


def read_prefix(path: Path, length: int = 64) -> bytes:
    with path.open("rb") as stream:
        return stream.read(length)


def read_suffix(path: Path, length: int = 64) -> bytes:
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - length))
        return stream.read(length)


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def printable_ascii(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)
