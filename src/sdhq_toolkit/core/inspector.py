from __future__ import annotations

from pathlib import Path

from ..formats.gpk.footer import FOOTER_SIZE, parse_stack_footer
from ..utils.binary import hex_bytes, printable_ascii, read_prefix, read_suffix
from ..utils.hashing import sha256_file


def inspect_archive(path: Path, header_size: int = 64, include_hash: bool = True) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    prefix = read_prefix(path, header_size)
    archive_size = path.stat().st_size
    footer = read_suffix(path, FOOTER_SIZE)
    result = {
        "name": path.name,
        "path": str(path),
        "size_bytes": archive_size,
        "header_hex": hex_bytes(prefix),
        "header_ascii": printable_ascii(prefix),
        "footer_hex": hex_bytes(footer),
        "footer_ascii": printable_ascii(footer),
        "stack_footer": parse_stack_footer(footer, archive_size),
    }
    result["sha256"] = sha256_file(path) if include_hash else None
    return result
