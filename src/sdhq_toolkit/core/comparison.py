from __future__ import annotations

from pathlib import Path

from ..utils.hashing import sha256_file


def compare_files(left: Path, right: Path, chunk_size: int = 1024 * 1024) -> dict:
    left = left.resolve()
    right = right.resolve()
    left_size = left.stat().st_size
    right_size = right.stat().st_size
    first_difference: int | None = None
    position = 0

    with left.open("rb") as left_stream, right.open("rb") as right_stream:
        while True:
            left_chunk = left_stream.read(chunk_size)
            right_chunk = right_stream.read(chunk_size)
            if left_chunk == right_chunk:
                if not left_chunk:
                    break
                position += len(left_chunk)
                continue
            limit = min(len(left_chunk), len(right_chunk))
            for index in range(limit):
                if left_chunk[index] != right_chunk[index]:
                    first_difference = position + index
                    break
            if first_difference is None:
                first_difference = position + limit
            break

    return {
        "left": str(left),
        "right": str(right),
        "left_size": left_size,
        "right_size": right_size,
        "left_sha256": sha256_file(left),
        "right_sha256": sha256_file(right),
        "identical": first_difference is None and left_size == right_size,
        "first_difference_offset": first_difference,
    }

