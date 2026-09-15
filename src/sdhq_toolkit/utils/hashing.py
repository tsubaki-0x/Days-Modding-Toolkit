from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable
from pathlib import Path

from .paths import safe_member_path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024, *, cancel=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            if cancel:
                cancel.check()
            digest.update(chunk)
    return digest.hexdigest()


def workspace_stat_fingerprint(root: Path, relative_paths: Iterable[str]) -> str:
    """Create a fast fingerprint for detecting workspace edits between batch runs."""

    digest = hashlib.sha256()
    for relative_path in relative_paths:
        path = safe_member_path(root, relative_path)
        encoded_path = relative_path.encode("utf-8", errors="surrogatepass")
        digest.update(struct.pack("<I", len(encoded_path)))
        digest.update(encoded_path)
        if path.is_file():
            stat = path.stat()
            digest.update(struct.pack("<QQ", stat.st_size, stat.st_mtime_ns))
        else:
            digest.update(b"M")
    return digest.hexdigest()
