#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Days CRio Universal Tool - standalone alpha backend for Days ModToolkit.

Lossless reference-based extractor/repacker for the CRio-family containers
observed in the original Japanese Summer Days (rUGP 5.7).

The object table is never synthesized. Repack starts from the exact original
container, preserves its header/tree/names/classes/counts, and patches only the
encoded payload offsets and sizes before writing every payload in preorder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import shutil
import struct
import sys
import tempfile
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Optional


TOOL_NAME = "Days CRio Universal Tool"
TOOL_VERSION = "1.0.0-alpha2"
PROJECT_FORMAT = "days-crio-project-v1"

PREFIX = bytes.fromhex(
    "cd 32 6e 59 14 00 00 00 ff ff 01 00 04 00 43 52 69 6f"
)
OFFSET_CONST = 0xA2FB6AD1
SIZE_CONST = 0xE7B5D9F8
MASK32 = 0xFFFFFFFF
MAX_PAYLOAD_SIZE = MASK32
SUPPORTED_NODE_FLAGS = {b"\x08\xC0\x00", b"\x18\xC0\x00"}

PNG_SIG = b"\x89PNG\r\n\x1a\n"
ASF_SIG = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
FOLDER_PAYLOAD = bytes.fromhex(
    "a4 cb f6 29 14 00 00 00 ff ff 01 00 0b 00 "
    "43 41 75 74 6f 46 6f 6c 64 65 72"
)


class CRioError(Exception):
    pass


@dataclass
class ObjectRecord:
    index: int
    parent_index: Optional[int]
    depth: int
    name: str
    name_raw_hex: str
    internal_path: str
    record_offset: int
    flags_hex: str
    class_tag: int
    class_schema: Optional[int]
    class_declared: Optional[str]
    encoded_offset_field: int
    encoded_offset: int
    encoded_size_field: int
    encoded_size: int
    child_count_field: int
    child_count: int
    payload_offset: int
    payload_size: int = 0
    payload_type: str = "UNKNOWN"
    payload_sha256: str = ""
    png_width: Optional[int] = None
    png_height: Optional[int] = None
    workspace_payload: Optional[str] = None
    storage_kind: Optional[str] = None


@dataclass
class ParsedContainer:
    path: Path
    size: int
    sha256: str
    root_count: int
    header_end: int
    header_sha256: str
    objects: list[ObjectRecord]
    repack_supported: bool
    limitations: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                return h.hexdigest()
            h.update(chunk)


def sha256_region(fh: BinaryIO, offset: int, size: int) -> str:
    h = hashlib.sha256()
    fh.seek(offset)
    remaining = size
    while remaining:
        chunk = fh.read(min(8 * 1024 * 1024, remaining))
        if not chunk:
            raise CRioError("unexpected EOF while hashing payload")
        h.update(chunk)
        remaining -= len(chunk)
    return h.hexdigest()


def copy_region(src: BinaryIO, dst: BinaryIO, offset: int, size: int) -> None:
    src.seek(offset)
    remaining = size
    while remaining:
        chunk = src.read(min(8 * 1024 * 1024, remaining))
        if not chunk:
            raise CRioError("unexpected EOF while extracting payload")
        dst.write(chunk)
        remaining -= len(chunk)


def copy_file_stream(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as inp, dst.open("wb") as out:
        shutil.copyfileobj(inp, out, length=8 * 1024 * 1024)


def u16(buf, offset: int) -> int:
    if offset + 2 > len(buf):
        raise CRioError(f"unexpected EOF reading uint16 at 0x{offset:X}")
    return struct.unpack_from("<H", buf, offset)[0]


def u32(buf, offset: int) -> int:
    if offset + 4 > len(buf):
        raise CRioError(f"unexpected EOF reading uint32 at 0x{offset:X}")
    return struct.unpack_from("<I", buf, offset)[0]


def decode_offset(encoded: int) -> int:
    return (encoded - OFFSET_CONST) & MASK32


def encode_offset(offset: int) -> int:
    if not 0 <= offset <= MASK32:
        raise CRioError(f"payload offset outside uint32 range: {offset}")
    return (offset + OFFSET_CONST) & MASK32


def rotate_left32(value: int, bits: int) -> int:
    value &= MASK32
    return ((value << bits) | (value >> (32 - bits))) & MASK32


def encode_size(size: int) -> int:
    if not 0 <= size <= MAX_PAYLOAD_SIZE:
        raise CRioError(
            f"payload size {size} (0x{size:X}) is outside the CRio uint32 range"
        )
    return (
        SIZE_CONST
        + rotate_left32(size, 13)
        + (size & 0xFFF)
    ) & MASK32


def decode_name(raw: bytes) -> str:
    for encoding in ("cp932", "shift_jis", "ascii"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp932", errors="replace")


def fs_safe_component(value: str) -> str:
    """Create a reversible-enough, Windows-safe workspace component.

    The exact original name is always retained in the manifest/header. This is
    only a host-filesystem projection and is never written back as a CRio name.
    """
    invalid = set('<>:"/\\|?*')
    out: list[str] = []
    for ch in value:
        code = ord(ch)
        if ch == "%":
            out.append("%25")
        elif ch in invalid or code < 32:
            raw = ch.encode("utf-8")
            out.extend(f"%{byte:02X}" for byte in raw)
        else:
            out.append(ch)
    result = "".join(out)
    while result.endswith((" ", ".")):
        tail = result[-1]
        result = result[:-1] + ("%20" if tail == " " else "%2E")
    if not result:
        result = "%00_EMPTY"
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if result.split(".", 1)[0].upper() in reserved:
        result = "%5F" + result
    return result


def is_crio(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(len(PREFIX)) == PREFIX
    except OSError:
        return False


def parse_png_bytes(blob: bytes) -> tuple[int, int, int]:
    if not blob.startswith(PNG_SIG):
        raise CRioError("not a PNG payload")
    pos = len(PNG_SIG)
    width = height = None
    while True:
        if pos + 12 > len(blob):
            raise CRioError("truncated PNG chunk header")
        length = struct.unpack_from(">I", blob, pos)[0]
        chunk_type = blob[pos + 4:pos + 8]
        data_start = pos + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(blob):
            raise CRioError("truncated PNG chunk payload")
        stored_crc = struct.unpack_from(">I", blob, data_end)[0]
        crc = zlib.crc32(chunk_type)
        crc = zlib.crc32(blob[data_start:data_end], crc) & MASK32
        if crc != stored_crc:
            raise CRioError(
                f"PNG CRC mismatch for {chunk_type!r}: "
                f"stored=0x{stored_crc:08X}, calculated=0x{crc:08X}"
            )
        if chunk_type == b"IHDR":
            if length != 13:
                raise CRioError("invalid PNG IHDR size")
            width, height = struct.unpack_from(">II", blob, data_start)
        pos = crc_end
        if chunk_type == b"IEND":
            if width is None or height is None:
                raise CRioError("PNG has no IHDR")
            return pos, width, height


def parse_png_file(path: Path) -> tuple[int, int, int]:
    return parse_png_bytes(path.read_bytes())


def detect_type(sample: bytes, class_declared: Optional[str]) -> str:
    if sample.startswith(PNG_SIG):
        return "PNG"
    if sample.startswith(b"OggS"):
        return "OGG"
    if sample.startswith(ASF_SIG):
        return "WMV_ASF"
    if sample.startswith(b"RIFF"):
        return "RIFF"
    if sample.startswith(b"BM"):
        return "BMP"
    if sample.startswith(b"DDS "):
        return "DDS"
    if sample.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if sample.startswith(b"PK\x03\x04"):
        return "ZIP"
    if sample.startswith(PREFIX):
        return "CRIO"
    if sample == FOLDER_PAYLOAD or class_declared == "CAutoFolder":
        return "FOLDER"
    if class_declared:
        return class_declared
    return "UNKNOWN"


def payload_sample(path: Path, offset: int, size: int, limit: int = 65536) -> bytes:
    with path.open("rb") as fh:
        fh.seek(offset)
        return fh.read(min(size, limit))


def parse_container(path: Path, *, validate_payloads: bool = True) -> ParsedContainer:
    path = path.resolve()
    size = path.stat().st_size
    if size < 20:
        raise CRioError("file is too small to be a CRio container")

    with path.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        if mm[:len(PREFIX)] != PREFIX:
            raise CRioError("CRio prefix does not match")
        root_count = u16(mm, 0x12)
        cursor = 0x14
        objects: list[ObjectRecord] = []

        def parse_node(parent_index: Optional[int], parent_path: str, depth: int) -> None:
            nonlocal cursor
            record_offset = cursor
            if cursor >= size:
                raise CRioError("object table runs beyond EOF")
            name_length = mm[cursor]
            cursor += 1
            if cursor + name_length > size:
                raise CRioError(f"truncated object name at 0x{record_offset:X}")
            raw_name = bytes(mm[cursor:cursor + name_length])
            cursor += name_length
            name = decode_name(raw_name)

            if cursor + 3 > size:
                raise CRioError("truncated object flags")
            flags = bytes(mm[cursor:cursor + 3])
            cursor += 3
            if flags not in SUPPORTED_NODE_FLAGS:
                raise CRioError(
                    f"unsupported node flags {flags.hex(' ')} at 0x{cursor - 3:X}"
                )

            class_tag = u16(mm, cursor)
            cursor += 2
            class_schema = None
            class_declared = None
            if class_tag == 0xFFFF:
                class_schema = u16(mm, cursor)
                cursor += 2
                if class_schema != 1:
                    raise CRioError(
                        f"unsupported class schema {class_schema} at 0x{cursor - 2:X}"
                    )
                class_length = u16(mm, cursor)
                cursor += 2
                if cursor + class_length > size:
                    raise CRioError("truncated class declaration")
                raw_class = bytes(mm[cursor:cursor + class_length])
                cursor += class_length
                try:
                    class_declared = raw_class.decode("ascii")
                except UnicodeDecodeError as exc:
                    raise CRioError("non-ASCII class declaration") from exc

            encoded_offset_field = cursor
            encoded_offset = u32(mm, cursor)
            cursor += 4
            encoded_size_field = cursor
            encoded_size = u32(mm, cursor)
            cursor += 4
            child_count_field = cursor
            child_count = u16(mm, cursor)
            cursor += 2

            internal_path = name if not parent_path else f"{parent_path}/{name}"
            record = ObjectRecord(
                index=len(objects),
                parent_index=parent_index,
                depth=depth,
                name=name,
                name_raw_hex=raw_name.hex(" "),
                internal_path=internal_path,
                record_offset=record_offset,
                flags_hex=flags.hex(" "),
                class_tag=class_tag,
                class_schema=class_schema,
                class_declared=class_declared,
                encoded_offset_field=encoded_offset_field,
                encoded_offset=encoded_offset,
                encoded_size_field=encoded_size_field,
                encoded_size=encoded_size,
                child_count_field=child_count_field,
                child_count=child_count,
                payload_offset=decode_offset(encoded_offset),
            )
            objects.append(record)
            my_index = record.index
            for _ in range(child_count):
                parse_node(my_index, internal_path, depth + 1)

        for _ in range(root_count):
            parse_node(None, "", 0)

        header_end = cursor
        if not objects:
            if header_end != size:
                raise CRioError("empty object table does not end at EOF")
        else:
            offsets = [obj.payload_offset for obj in objects]
            if offsets[0] != header_end:
                raise CRioError(
                    f"first payload begins at 0x{offsets[0]:X}; "
                    f"header ends at 0x{header_end:X}"
                )
            if offsets != sorted(offsets):
                raise CRioError("payload offsets are not monotonic in object preorder")
            if any(offset < header_end or offset > size for offset in offsets):
                raise CRioError("decoded payload offset is outside the data region")

        limitations: list[str] = []
        repack_supported = True
        for index, obj in enumerate(objects):
            next_offset = objects[index + 1].payload_offset if index + 1 < len(objects) else size
            if next_offset < obj.payload_offset:
                raise CRioError(f"negative payload span for object {obj.index}")
            obj.payload_size = next_offset - obj.payload_offset
            if obj.payload_size > MAX_PAYLOAD_SIZE:
                repack_supported = False
                limitations.append(
                    f"object {obj.index} payload is 0x{obj.payload_size:X}; "
                    "payload exceeds the CRio uint32 size range"
                )
            else:
                expected_encoded_size = encode_size(obj.payload_size)
                if obj.encoded_size != expected_encoded_size:
                    raise CRioError(
                        f"encoded size mismatch at object {obj.index} {obj.internal_path!r}: "
                        f"header=0x{obj.encoded_size:08X}, "
                        f"expected=0x{expected_encoded_size:08X}, "
                        f"actual={obj.payload_size}"
                    )

            sample = bytes(mm[obj.payload_offset:obj.payload_offset + min(obj.payload_size, 65536)])
            obj.payload_type = detect_type(sample, obj.class_declared)
            obj.payload_sha256 = sha256_region(
                fh, obj.payload_offset, obj.payload_size
            )

            if validate_payloads and obj.payload_type == "PNG":
                payload = bytes(
                    mm[obj.payload_offset:obj.payload_offset + obj.payload_size]
                )
                exact, width, height = parse_png_bytes(payload)
                if exact != len(payload):
                    raise CRioError(
                        f"PNG {obj.internal_path!r} has {len(payload) - exact} "
                        "extra byte(s) after IEND"
                    )
                obj.png_width = width
                obj.png_height = height
            elif validate_payloads and obj.payload_type == "FOLDER":
                payload = bytes(
                    mm[obj.payload_offset:obj.payload_offset + obj.payload_size]
                )
                if payload != FOLDER_PAYLOAD:
                    raise CRioError(
                        f"CAutoFolder payload differs from the confirmed structure: "
                        f"{obj.internal_path!r}"
                    )

        header = bytes(mm[:header_end])
        full_hash = hashlib.sha256(mm).hexdigest()
        return ParsedContainer(
            path=path,
            size=size,
            sha256=full_hash,
            root_count=root_count,
            header_end=header_end,
            header_sha256=hashlib.sha256(header).hexdigest(),
            objects=objects,
            repack_supported=repack_supported,
            limitations=sorted(set(limitations)),
        )


