from __future__ import annotations

import struct


INDEX_SIGNATURE = b"STKFile0PIDX"
ARCHIVE_SIGNATURE = b"STKFile0PACKFILE"
FOOTER_SIZE = 32


def parse_stack_footer(footer: bytes, archive_size: int) -> dict:
    result = {
        "format": "UNKNOWN",
        "valid": False,
        "index_signature": None,
        "archive_signature": None,
        "index_size": None,
        "index_offset": None,
    }
    if len(footer) != FOOTER_SIZE:
        return result

    index_signature = footer[:12]
    archive_signature = footer[16:32]
    index_size = struct.unpack_from("<I", footer, 12)[0]
    result.update(
        {
            "index_signature": index_signature.decode("ascii", errors="replace"),
            "archive_signature": archive_signature.decode("ascii", errors="replace"),
            "index_size": index_size,
        }
    )

    if index_signature != INDEX_SIGNATURE or archive_signature != ARCHIVE_SIGNATURE:
        return result

    index_offset = archive_size - FOOTER_SIZE - index_size
    if index_offset < 0:
        return result

    result.update(
        {
            "format": "GPK/STACK",
            "valid": True,
            "index_offset": index_offset,
        }
    )
    return result
