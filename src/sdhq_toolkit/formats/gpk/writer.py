from __future__ import annotations

import json
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

from .footer import ARCHIVE_SIGNATURE, INDEX_SIGNATURE
from .index import read_stack_index, xor_with_repeating_key
from ...utils.hashing import sha256_file, workspace_stat_fingerprint
from ...utils.paths import safe_member_path
from ...utils.streams import DEFAULT_CHUNK_SIZE, copy_exact


EntryProgress = Callable[[int, int, str, bool], None]


class GPKWriter:
    """Reference-based Stack GPK writer.

    The writer preserves the PE prefix, entry order, filenames and unknown
    fields from the legitimate original archive. Adding or removing entries is
    intentionally unsupported in this stage.
    """

    def __init__(self, reference: Path, key: bytes) -> None:
        self.reference = reference.resolve()
        self.key = key

    @staticmethod
    def _serialize_entry(entry: dict) -> bytes:
        encoded_name = entry["path"].encode("utf-16le")
        name_units = len(encoded_name) // 2
        header = entry["header"]
        if name_units > 0xFFFF or len(header) > 0xFF:
            raise ValueError(f"Entry metadata exceeds format limits: {entry['path']}")
        return (
            struct.pack("<H", name_units)
            + encoded_name
            + struct.pack(
                "<ihIIiIB",
                entry["unknown_1"],
                entry["unknown_2"],
                entry["offset"],
                entry["stored_size"],
                entry["unknown_3"],
                entry["unpacked_size"],
                len(header),
            )
            + header
        )

    @staticmethod
    def _compress_modified_entry(
        input_path: Path,
        rebuilt,
        header_size: int,
        *,
        chunk_size: int,
        cancel=None,
    ) -> tuple[bytes, int, int]:
        compressor = zlib.compressobj(level=9)
        prefix = bytearray()
        body_size = 0

        def consume_compressed(data: bytes) -> None:
            nonlocal body_size
            if not data:
                return
            if len(prefix) < header_size:
                needed = header_size - len(prefix)
                prefix.extend(data[:needed])
                data = data[needed:]
            if data:
                rebuilt.write(data)
                body_size += len(data)

        unpacked_size = 0
        with input_path.open("rb") as input_stream:
            while chunk := input_stream.read(chunk_size):
                if cancel:
                    cancel.check()
                unpacked_size += len(chunk)
                consume_compressed(compressor.compress(chunk))
        consume_compressed(compressor.flush())
        if len(prefix) != header_size:
            raise ValueError(f"Modified entry is smaller than its preserved header: {input_path}")
        return bytes(prefix), header_size + body_size, unpacked_size

    @staticmethod
    def _copy_modified_unpacked_entry(
        input_path: Path,
        rebuilt,
        header_size: int,
        *,
        chunk_size: int,
        cancel=None,
    ) -> tuple[bytes, int]:
        stored_size = input_path.stat().st_size
        if stored_size < header_size:
            raise ValueError(f"Modified entry is smaller than its preserved header: {input_path}")
        with input_path.open("rb") as input_stream:
            header = input_stream.read(header_size)
            copy_exact(input_stream, rebuilt, stored_size - header_size, chunk_size=chunk_size, cancel=cancel)
        return header, stored_size

    def repack(
        self,
        source_directory: Path,
        output: Path,
        *,
        progress: EntryProgress | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        cancel=None,
        expected_hashes=None,
        overlay_metadata=None,
    ) -> dict:
        source_directory = source_directory.resolve()
        output = output.resolve()
        reference_stat = self.reference.stat()
        if output == self.reference:
            raise ValueError("Output must not overwrite the reference archive")
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")

        metadata_path = source_directory / ".sdhq" / "archive.json"
        if overlay_metadata is None and not metadata_path.is_file():
            raise FileNotFoundError(f"Missing extraction metadata: {metadata_path}")
        metadata = overlay_metadata if overlay_metadata is not None else json.loads(metadata_path.read_text(encoding="utf-8"))
        reference = read_stack_index(self.reference, self.key)
        from ...core.partial import check_reference
        check_reference(metadata, reference)
        reference_entries = reference["entries"]
        metadata_entries = metadata.get("entries", [])
        if len(reference_entries) != len(metadata_entries):
            raise ValueError("Reference archive and extraction metadata have different entry counts")

        metadata_by_path = {entry["path"]: entry for entry in metadata_entries}
        if len(metadata_by_path) != len(metadata_entries):
            raise ValueError("Duplicate paths in extraction metadata")
        if [entry["path"] for entry in reference_entries] != [entry["path"] for entry in metadata_entries]:
            raise ValueError("Reference archive and extraction metadata have different entry order or paths")

        declared = {safe_member_path(source_directory, entry["path"]) for entry in metadata_entries}
        for path in source_directory.rglob("*"):
            if cancel:
                cancel.check()
            if path.is_file() and ".sdhq" not in path.relative_to(source_directory).parts and path.resolve() not in declared:
                if overlay_metadata is None:
                    raise ValueError(f"New GPK entries are not supported: {path}")

        first_offset = min(entry["offset"] for entry in reference_entries)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        if temporary.exists():
            raise FileExistsError(f"Temporary output already exists: {temporary}")

        build_entries: list[dict] = []
        modified_count = 0
        try:
            with self.reference.open("rb") as original, temporary.open("xb") as rebuilt:
                copy_exact(original, rebuilt, first_offset, chunk_size=chunk_size, cancel=cancel)
                for index, original_entry in enumerate(reference_entries):
                    if cancel:
                        cancel.check()
                    metadata_entry = metadata_by_path[original_entry["path"]]
                    input_path = safe_member_path(source_directory, original_entry["path"])
                    extracted = metadata_entry.get("extracted", True)
                    if not extracted and input_path.exists() and (overlay_metadata is None or input_path.is_file()):
                        raise ValueError(f"Untracked file at unextracted entry: {input_path}")
                    if extracted and not input_path.is_file():
                        raise FileNotFoundError(f"Missing extracted entry: {input_path}")
                    input_stat = input_path.stat() if extracted else None
                    current_hash = sha256_file(input_path, chunk_size=chunk_size, cancel=cancel) if extracted else None
                    if expected_hashes is not None and current_hash != expected_hashes.get(original_entry["path"]):
                        raise ValueError(f"Workspace changed since validation: {input_path}")
                    modified = extracted and current_hash != metadata_entry.get("extracted_sha256")
                    original_header = bytes.fromhex(original_entry["header_hex"])
                    body_start = original_entry["offset"]
                    if index + 1 < len(reference_entries):
                        body_end = reference_entries[index + 1]["offset"]
                    else:
                        body_end = reference["index_offset"]
                    original_body_size = body_end - body_start
                    expected_body_size = original_entry["stored_size"] - len(original_header)
                    if original_body_size != expected_body_size:
                        raise ValueError(
                            f"Unsupported entry layout for {original_entry['path']}: "
                            f"physical={original_body_size}, expected={expected_body_size}"
                        )

                    if modified:
                        modified_count += 1
                        if original_entry["is_packed"]:
                            if original_entry["compression_tag"] != "DFLT":
                                raise ValueError(f"Unsupported compression: {original_entry['path']}")
                            header, stored_size, unpacked_size = self._compress_modified_entry(
                                input_path,
                                rebuilt,
                                len(original_header),
                                chunk_size=chunk_size,
                                cancel=cancel,
                            )
                        else:
                            header, stored_size = self._copy_modified_unpacked_entry(
                                input_path,
                                rebuilt,
                                min(len(original_header), input_stat.st_size) if overlay_metadata is not None else len(original_header),
                                chunk_size=chunk_size,
                                cancel=cancel,
                            )
                            unpacked_size = 0
                    else:
                        original.seek(body_start)
                        copy_exact(original, rebuilt, original_body_size, chunk_size=chunk_size, cancel=cancel)
                        header = original_header
                        stored_size = original_entry["stored_size"]
                        unpacked_size = original_entry["unpacked_size"]

                    new_offset = rebuilt.tell() - (stored_size - len(header))
                    if extracted:
                        after = input_path.stat()
                        if (after.st_size, after.st_mtime_ns) != (input_stat.st_size, input_stat.st_mtime_ns):
                            raise ValueError(f"Workspace changed during repack: {input_path}")
                    build_entries.append(
                        {
                            "path": original_entry["path"],
                            "unknown_1": original_entry["unknown_1"],
                            "unknown_2": original_entry["unknown_2"],
                            "offset": new_offset,
                            "stored_size": stored_size,
                            "unknown_3": original_entry["unknown_3"],
                            "unpacked_size": unpacked_size,
                            "header": header,
                            "modified": modified,
                        }
                    )
                    if progress is not None:
                        progress(index + 1, len(reference_entries), original_entry["path"], modified)

                raw_index = (
                    b"".join(self._serialize_entry(entry) for entry in build_entries)
                    + bytes.fromhex(reference["index_trailer_hex"])
                )
                original_prefix = bytes.fromhex(reference["index_prefix_hex"])
                encrypted_index = xor_with_repeating_key(
                    original_prefix + zlib.compress(raw_index, level=9),
                    self.key,
                )
                rebuilt.write(encrypted_index)
                rebuilt.write(INDEX_SIGNATURE)
                rebuilt.write(struct.pack("<I", len(encrypted_index)))
                rebuilt.write(ARCHIVE_SIGNATURE)

            validation = read_stack_index(temporary, self.key)
            if cancel:
                cancel.check()
            if validation["entry_count"] != len(reference_entries):
                raise ValueError("Rebuilt archive validation failed")
            after_reference = self.reference.stat()
            if (reference_stat.st_size, reference_stat.st_mtime_ns, reference_stat.st_ctime_ns) != (after_reference.st_size, after_reference.st_mtime_ns, after_reference.st_ctime_ns):
                raise ValueError("Reference changed during repack; retry with a stable reference")
            temporary.replace(output)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise

        return {
            "format": "GPK/STACK",
            "reference": str(self.reference),
            "source_directory": str(source_directory),
            "output": str(output),
            "entry_count": len(build_entries),
            "modified_entries": modified_count,
            "unchanged_entries": len(build_entries) - modified_count,
            "output_size": output.stat().st_size,
            "index_size": validation["index_size"],
            "workspace_stat_fingerprint": workspace_stat_fingerprint(
                source_directory,
                (entry["path"] for entry in metadata_entries),
            ),
            "streaming": True,
            "validation": "PASS",
        }
