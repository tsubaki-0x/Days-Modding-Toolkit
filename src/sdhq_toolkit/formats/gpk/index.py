from __future__ import annotations

import json
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from .footer import FOOTER_SIZE, parse_stack_footer
from ...utils.binary import read_suffix
from ...utils.paths import safe_member_path


@dataclass(slots=True)
class StackIndexEntry:
    path: str
    unknown_1: int
    unknown_2: int
    offset: int
    stored_size: int
    unknown_3: int
    compression_tag: str
    unpacked_size: int
    is_packed: bool
    header_hex: str


def xor_with_repeating_key(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("CIPHERCODE key is empty")
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def _take(data: bytes, cursor: int, size: int) -> tuple[bytes, int]:
    end = cursor + size
    if end > len(data):
        raise ValueError("Truncated Stack GPK index")
    return data[cursor:end], end


def _parse_decompressed_index(data: bytes, archive_size: int) -> tuple[list[StackIndexEntry], bytes]:
    entries: list[StackIndexEntry] = []
    cursor = 0
    while cursor < len(data):
        entry_start = cursor
        raw, cursor = _take(data, cursor, 2)
        name_units = struct.unpack("<H", raw)[0]
        if name_units == 0:
            if not entries:
                raise ValueError("Stack GPK index contains no entries")
            return entries, data[entry_start:]
        raw_name, cursor = _take(data, cursor, name_units * 2)
        name = raw_name.decode("utf-16le")
        safe_member_path(Path("."), name)

        fixed, cursor = _take(data, cursor, 23)
        unknown_1, unknown_2, offset, stored_size, unknown_3, unpacked_size, header_size = struct.unpack(
            "<ihIIiIB", fixed
        )
        raw_header, cursor = _take(data, cursor, header_size)
        if offset < 0 or stored_size < 0 or offset + stored_size > archive_size:
            raise ValueError(f"Invalid placement for entry: {name}")
        entries.append(
            StackIndexEntry(
                path=name,
                unknown_1=unknown_1,
                unknown_2=unknown_2,
                offset=offset,
                stored_size=stored_size,
                unknown_3=unknown_3,
                compression_tag=struct.pack("<I", unknown_3 & 0xFFFFFFFF).decode("ascii", errors="replace"),
                unpacked_size=unpacked_size,
                is_packed=unpacked_size != 0,
                header_hex=raw_header.hex().upper(),
            )
        )
    if not entries:
        raise ValueError("Stack GPK index contains no entries")
    return entries, b""


def parse_decompressed_index(data: bytes, archive_size: int) -> list[StackIndexEntry]:
    entries, _trailer = _parse_decompressed_index(data, archive_size)
    return entries


def read_stack_index(archive: Path, key: bytes) -> dict:
    archive = archive.resolve()
    archive_size = archive.stat().st_size
    footer = read_suffix(archive, FOOTER_SIZE)
    footer_data = parse_stack_footer(footer, archive_size)
    if not footer_data["valid"]:
        raise ValueError("Archive does not have a valid GPK/STACK footer")

    index_size = footer_data["index_size"]
    index_offset = footer_data["index_offset"]
    with archive.open("rb") as stream:
        stream.seek(index_offset)
        encrypted_index = stream.read(index_size)
    if len(encrypted_index) != index_size:
        raise ValueError("Could not read the complete encrypted index")

    decrypted = xor_with_repeating_key(encrypted_index, key)
    if len(decrypted) < 5:
        raise ValueError("Decrypted index is too short")
    try:
        decompressed = zlib.decompress(decrypted[4:])
    except zlib.error as exc:
        raise ValueError("Index decryption or Zlib decompression failed; check CIPHERCODE") from exc

    entries, trailer = _parse_decompressed_index(decompressed, archive_size)
    return {
        "archive": str(archive),
        "format": "GPK/STACK",
        "archive_size": archive_size,
        "index_size": index_size,
        "index_offset": index_offset,
        "decompressed_index_size": len(decompressed),
        "index_prefix_hex": decrypted[:4].hex().upper(),
        "index_prefix_uint32": struct.unpack("<I", decrypted[:4])[0],
        "index_trailer_hex": trailer.hex().upper(),
        "entry_count": len(entries),
        "packed_entries": sum(entry.is_packed for entry in entries),
        "unpacked_entries": sum(not entry.is_packed for entry in entries),
        "entries": [asdict(entry) for entry in entries],
    }


def load_key_report(path: Path) -> bytes:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report.get("found") or not report.get("key_hex"):
        raise ValueError("CIPHERCODE was not found in the supplied report")
    try:
        return bytes.fromhex(report["key_hex"])
    except ValueError as exc:
        raise ValueError("Invalid key_hex in CIPHERCODE report") from exc


def save_index_report(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
