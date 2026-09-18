from __future__ import annotations

import json
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from .footer import FOOTER_SIZE, parse_stack_footer
from ...utils.binary import read_suffix
from ...utils.paths import safe_member_path


# Known repeating XOR keys used by the Stack PIDX variants confirmed by this
# project. A caller-supplied/CIPHERCODE key is always tried first; these values
# are fallbacks so an archive can identify itself by successfully decoding.
KNOWN_INDEX_KEYS: tuple[tuple[str, bytes], ...] = (
    (
        "SCHOOL_DAYS_HQ",
        bytes.fromhex("82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49"),
    ),
    (
        "ALT_56",
        bytes.fromhex("56 7C 1B 90 B6 FE 3F DB B6 06 79 EA CC 11 A0 4F"),
    ),
    (
        "SHINY_DAYS",
        bytes.fromhex("F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA"),
    ),
)


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
        raise ValueError("CIPHERCODE/PIDX key is empty")
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


def _key_name(key: bytes | None) -> str:
    if key is None:
        return "NO_XOR"
    for name, known in KNOWN_INDEX_KEYS:
        if key == known:
            return name
    return "SUPPLIED"


def _candidate_keys(key: bytes | None):
    candidates: list[tuple[str, bytes | None]] = []
    seen: set[bytes | None] = set()

    if key is not None:
        candidates.append((_key_name(key), key))
        seen.add(key)

    for name, known in KNOWN_INDEX_KEYS:
        if known not in seen:
            candidates.append((name, known))
            seen.add(known)

    # Kept as a final compatibility probe. Confirmed game archives currently
    # use XOR, but accepting a plain PIDX costs nothing and keeps the parser
    # defensive for related Stack archives.
    candidates.append(("NO_XOR", None))
    return candidates


def _decode_stack_index(
    encrypted_index: bytes,
    archive_size: int,
    preferred_key: bytes | None,
) -> tuple[list[StackIndexEntry], bytes, bytes, str, bytes | None]:
    failures: list[str] = []

    for key_name, candidate in _candidate_keys(preferred_key):
        transformed = (
            encrypted_index
            if candidate is None
            else xor_with_repeating_key(encrypted_index, candidate)
        )
        if len(transformed) < 5:
            failures.append(f"{key_name}: decoded PIDX is too short")
            continue

        declared_size = struct.unpack("<I", transformed[:4])[0]
        try:
            decompressed = zlib.decompress(transformed[4:])
        except zlib.error:
            failures.append(f"{key_name}: zlib rejected the PIDX")
            continue

        if len(decompressed) != declared_size:
            failures.append(
                f"{key_name}: PIDX size {len(decompressed)} != declared {declared_size}"
            )
            continue

        try:
            entries, trailer = _parse_decompressed_index(decompressed, archive_size)
        except (ValueError, UnicodeError, struct.error) as exc:
            failures.append(f"{key_name}: invalid index structure ({exc})")
            continue

        return entries, trailer, transformed[:4], key_name, candidate

    raise ValueError(
        "Index decryption/decompression failed for the supplied key and all "
        "known School Days HQ / Shiny Days PIDX variants.\n  "
        + "\n  ".join(failures)
    )


def read_stack_index(archive: Path, key: bytes | None = None) -> dict:
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

    entries, trailer, prefix, key_name, effective_key = _decode_stack_index(
        encrypted_index,
        archive_size,
        key,
    )
    return {
        "archive": str(archive),
        "format": "GPK/STACK",
        "archive_size": archive_size,
        "index_size": index_size,
        "index_offset": index_offset,
        "decompressed_index_size": struct.unpack("<I", prefix)[0],
        "index_prefix_hex": prefix.hex().upper(),
        "index_prefix_uint32": struct.unpack("<I", prefix)[0],
        "index_trailer_hex": trailer.hex().upper(),
        "index_key_name": key_name,
        "index_key_hex": effective_key.hex().upper() if effective_key else "",
        "index_xor": effective_key is not None,
        "index_codec": "zlib",
        "entry_count": len(entries),
        "packed_entries": sum(entry.is_packed for entry in entries),
        "unpacked_entries": sum(not entry.is_packed for entry in entries),
        "entries": [asdict(entry) for entry in entries],
    }


def load_key_report(path: Path) -> bytes:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report.get("found") or not report.get("key_hex"):
        raise ValueError("CIPHERCODE/PIDX key was not found in the supplied report")
    try:
        return bytes.fromhex(report["key_hex"])
    except ValueError as exc:
        raise ValueError("Invalid key_hex in CIPHERCODE/PIDX report") from exc


def save_index_report(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
