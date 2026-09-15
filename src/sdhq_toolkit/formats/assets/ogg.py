from __future__ import annotations

import struct
from pathlib import Path


OGG_CAPTURE = b"OggS"
OGG_POLYNOMIAL = 0x04C11DB7


def _crc_table() -> tuple[int, ...]:
    table = []
    for value in range(256):
        remainder = value << 24
        for _ in range(8):
            remainder = ((remainder << 1) ^ OGG_POLYNOMIAL) & 0xFFFFFFFF if (
                remainder & 0x80000000
            ) else (remainder << 1) & 0xFFFFFFFF
        table.append(remainder)
    return tuple(table)


OGG_CRC_TABLE = _crc_table()


def ogg_crc(data: bytes) -> int:
    checksum = 0
    for value in data:
        checksum = ((checksum << 8) & 0xFFFFFFFF) ^ OGG_CRC_TABLE[((checksum >> 24) & 0xFF) ^ value]
    return checksum


def _codec_from_packet(packet: bytes) -> dict:
    if packet.startswith(b"\x01vorbis") and len(packet) >= 30:
        version = struct.unpack_from("<I", packet, 7)[0]
        channels = packet[11]
        sample_rate = struct.unpack_from("<I", packet, 12)[0]
        if version != 0 or channels == 0 or sample_rate == 0 or packet[29] & 1 != 1:
            raise ValueError("Invalid Vorbis identification header")
        return {
            "codec": "Vorbis",
            "channels": channels,
            "sample_rate": sample_rate,
            "nominal_bitrate": struct.unpack_from("<i", packet, 20)[0],
        }
    if packet.startswith(b"OpusHead") and len(packet) >= 19:
        channels = packet[9]
        if channels == 0:
            raise ValueError("Invalid Opus identification header")
        return {
            "codec": "Opus",
            "channels": channels,
            "sample_rate": 48000,
            "input_sample_rate": struct.unpack_from("<I", packet, 12)[0],
        }
    if packet.startswith(b"\x80theora"):
        return {"codec": "Theora", "channels": None, "sample_rate": None}
    raise ValueError("Unsupported Ogg codec identification packet")


def inspect_ogg(path: Path, *, full_validation: bool = False) -> dict:
    first_packet: bytearray | None = bytearray()
    codec: dict | None = None
    page_count = 0
    last_granule = 0
    serial_sequences: dict[int, int] = {}
    with path.open("rb") as stream:
        while True:
            header = stream.read(27)
            if not header:
                break
            if len(header) != 27 or header[:4] != OGG_CAPTURE:
                raise ValueError("Invalid or truncated Ogg page header")
            if header[4] != 0:
                raise ValueError(f"Unsupported Ogg bitstream version: {header[4]}")
            segment_count = header[26]
            lacing = stream.read(segment_count)
            if len(lacing) != segment_count:
                raise ValueError("Truncated Ogg segment table")
            payload_size = sum(lacing)
            payload = stream.read(payload_size)
            if len(payload) != payload_size:
                raise ValueError("Truncated Ogg page payload")
            page_count += 1
            granule = struct.unpack_from("<Q", header, 6)[0]
            if granule != 0xFFFFFFFFFFFFFFFF:
                last_granule = max(last_granule, granule)
            serial = struct.unpack_from("<I", header, 14)[0]
            sequence = struct.unpack_from("<I", header, 18)[0]
            expected = serial_sequences.get(serial)
            if full_validation and expected is not None and sequence != expected:
                raise ValueError(
                    f"Ogg page sequence mismatch for serial {serial}: expected {expected}, got {sequence}"
                )
            serial_sequences[serial] = sequence + 1
            if full_validation:
                stored_crc = struct.unpack_from("<I", header, 22)[0]
                checksum_header = bytearray(header)
                checksum_header[22:26] = b"\x00\x00\x00\x00"
                calculated_crc = ogg_crc(bytes(checksum_header) + lacing + payload)
                if stored_crc != calculated_crc:
                    raise ValueError(f"Ogg CRC mismatch on page {page_count}")
            if first_packet is not None:
                cursor = 0
                for segment_size in lacing:
                    first_packet.extend(payload[cursor : cursor + segment_size])
                    if segment_size < 255:
                        codec = _codec_from_packet(bytes(first_packet))
                        first_packet = None
                    cursor += segment_size
                    if first_packet is None:
                        break
            if not full_validation and first_packet is None:
                break
    if page_count == 0 or first_packet is not None or codec is None:
        raise ValueError("Ogg stream has no complete identification packet")
    duration = None
    if full_validation and codec.get("sample_rate") and last_granule:
        duration = last_granule / codec["sample_rate"]
    return {
        "format": "Ogg",
        "size_bytes": path.stat().st_size,
        **codec,
        "page_count": page_count if full_validation else None,
        "duration_seconds": duration,
        "full_validation": full_validation,
    }


def compare_ogg_compatibility(original: dict, modified: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for field, label in (("codec", "codec"), ("channels", "channel count"), ("sample_rate", "sample rate")):
        if modified.get(field) != original.get(field):
            errors.append(f"{label} changed from {original.get(field)} to {modified.get(field)}")
    if modified.get("nominal_bitrate") != original.get("nominal_bitrate"):
        warnings.append(
            f"nominal bitrate changed from {original.get('nominal_bitrate')} to "
            f"{modified.get('nominal_bitrate')}"
        )
    return errors, warnings
