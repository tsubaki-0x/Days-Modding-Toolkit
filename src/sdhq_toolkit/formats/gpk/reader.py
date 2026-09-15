from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Callable
from pathlib import Path

from .index import read_stack_index
from ...utils.paths import safe_member_path
from ...utils.streams import DEFAULT_CHUNK_SIZE


EntryProgress = Callable[[int, int, str, int], None]


class GPKReader:
    """Read and extract confirmed Stack GPK archives."""

    def __init__(self, archive: Path, key: bytes) -> None:
        self.archive = archive.resolve()
        self.key = key

    def extract(
        self,
        destination: Path,
        *,
        progress: EntryProgress | None = None,
        index_report: dict | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        cancel=None,
    ) -> dict:
        destination = destination.resolve()
        if destination.exists() and any(destination.iterdir()):
            raise ValueError(f"Destination is not empty: {destination}")
        destination.mkdir(parents=True, exist_ok=True)

        report = index_report if index_report is not None else read_stack_index(self.archive, self.key)
        extracted_entries: list[dict] = []
        with self.archive.open("rb") as stream:
            total_entries = len(report["entries"])
            for entry_index, entry in enumerate(report["entries"], start=1):
                if cancel:
                    cancel.check()
                header = bytes.fromhex(entry["header_hex"])
                body_size = entry["stored_size"] - len(header)
                if body_size < 0:
                    raise ValueError(f"Header exceeds stored size: {entry['path']}")
                stream.seek(entry["offset"])
                output_path = safe_member_path(destination, entry["path"])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = output_path.with_name(output_path.name + ".sdhq-part")
                if output_path.exists() or temporary_path.exists():
                    raise FileExistsError(f"Extraction target already exists: {output_path}")

                digest = hashlib.sha256()
                extracted_size = 0
                remaining = body_size
                try:
                    with temporary_path.open("xb") as output_stream:
                        if entry["is_packed"]:
                            decompressor = zlib.decompressobj()

                            def consume_compressed(data: bytes) -> None:
                                nonlocal extracted_size
                                pending = data
                                while pending:
                                    if cancel:
                                        cancel.check()
                                    try:
                                        unpacked = decompressor.decompress(pending, chunk_size)
                                    except zlib.error as exc:
                                        raise ValueError(f"Invalid Deflate data: {entry['path']}") from exc
                                    pending = decompressor.unconsumed_tail
                                    if unpacked:
                                        output_stream.write(unpacked)
                                        digest.update(unpacked)
                                        extracted_size += len(unpacked)
                                    if not unpacked and not pending:
                                        break

                            consume_compressed(header)
                            while remaining:
                                if cancel:
                                    cancel.check()
                                chunk = stream.read(min(chunk_size, remaining))
                                if not chunk:
                                    raise ValueError(f"Truncated archive entry: {entry['path']}")
                                remaining -= len(chunk)
                                consume_compressed(chunk)
                            tail = decompressor.flush()
                            if tail:
                                output_stream.write(tail)
                                digest.update(tail)
                                extracted_size += len(tail)
                            if not decompressor.eof or decompressor.unused_data:
                                raise ValueError(f"Incomplete or trailing Deflate data: {entry['path']}")
                            if extracted_size != entry["unpacked_size"]:
                                raise ValueError(
                                    f"Unpacked size mismatch for {entry['path']}: "
                                    f"expected {entry['unpacked_size']}, got {extracted_size}"
                                )
                        else:
                            output_stream.write(header)
                            digest.update(header)
                            extracted_size += len(header)
                            while remaining:
                                if cancel:
                                    cancel.check()
                                chunk = stream.read(min(chunk_size, remaining))
                                if not chunk:
                                    raise ValueError(f"Truncated archive entry: {entry['path']}")
                                remaining -= len(chunk)
                                output_stream.write(chunk)
                                digest.update(chunk)
                                extracted_size += len(chunk)
                    temporary_path.replace(output_path)
                except Exception:
                    if temporary_path.exists():
                        temporary_path.unlink()
                    raise

                extracted_entries.append(
                    {
                        **entry,
                        "archive_body_size": body_size,
                        "extracted_size": extracted_size,
                        "extracted_sha256": digest.hexdigest(),
                    }
                )
                if progress is not None:
                    progress(entry_index, total_entries, entry["path"], extracted_size)

        metadata = {
            "format": "GPK/STACK",
            "source_archive": str(self.archive),
            "archive_size": report["archive_size"],
            "index_size": report["index_size"],
            "index_offset": report["index_offset"],
            "entry_count": report["entry_count"],
            "source_mtime_ns": self.archive.stat().st_mtime_ns,
            "streaming": True,
            "entries": extracted_entries,
        }
        metadata_path = destination / ".sdhq" / "archive.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata
