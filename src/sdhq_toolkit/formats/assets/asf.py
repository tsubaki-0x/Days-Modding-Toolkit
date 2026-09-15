from __future__ import annotations

import struct
import uuid
from pathlib import Path


def _guid(value: str) -> bytes:
    return uuid.UUID(value).bytes_le


ASF_HEADER_OBJECT = _guid("75B22630-668E-11CF-A6D9-00AA0062CE6C")
ASF_FILE_PROPERTIES = _guid("8CABDCA1-A947-11CF-8EE4-00C00C205365")
ASF_STREAM_PROPERTIES = _guid("B7DC0791-A9B7-11CF-8EE6-00C00C205365")
ASF_AUDIO_MEDIA = _guid("F8699E40-5B4D-11CF-A8FD-00805F5C442B")
ASF_VIDEO_MEDIA = _guid("BC19EFC0-5B4D-11CF-A8FD-00805F5C442B")
MAX_ASF_HEADER = 64 * 1024 * 1024


def _fourcc(value: bytes) -> str:
    return value.decode("ascii", errors="replace").rstrip("\x00")


def inspect_asf(path: Path, *, full_validation: bool = False) -> dict:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        prefix = stream.read(30)
        if len(prefix) != 30 or prefix[:16] != ASF_HEADER_OBJECT:
            raise ValueError("Invalid or truncated ASF header object")
        header_size = struct.unpack_from("<Q", prefix, 16)[0]
        object_count = struct.unpack_from("<I", prefix, 24)[0]
        if header_size < 30 or header_size > file_size or header_size > MAX_ASF_HEADER:
            raise ValueError(f"Invalid ASF header size: {header_size}")
        stream.seek(0)
        header = stream.read(header_size)
    if len(header) != header_size:
        raise ValueError("Truncated ASF header")

    file_properties: dict | None = None
    streams: list[dict] = []
    cursor = 30
    parsed_objects = 0
    while parsed_objects < object_count:
        if cursor + 24 > len(header):
            raise ValueError("Truncated ASF header subobject")
        object_guid = header[cursor : cursor + 16]
        object_size = struct.unpack_from("<Q", header, cursor + 16)[0]
        if object_size < 24 or cursor + object_size > len(header):
            raise ValueError(f"Invalid ASF subobject size at offset {cursor}: {object_size}")
        payload = header[cursor + 24 : cursor + object_size]
        if object_guid == ASF_FILE_PROPERTIES:
            if len(payload) < 80:
                raise ValueError("Truncated ASF File Properties object")
            file_properties = {
                "declared_file_size": struct.unpack_from("<Q", payload, 16)[0],
                "data_packets": struct.unpack_from("<Q", payload, 32)[0],
                "play_duration_100ns": struct.unpack_from("<Q", payload, 40)[0],
                "preroll_ms": struct.unpack_from("<Q", payload, 56)[0],
                "flags": struct.unpack_from("<I", payload, 64)[0],
                "min_packet_size": struct.unpack_from("<I", payload, 68)[0],
                "max_packet_size": struct.unpack_from("<I", payload, 72)[0],
                "max_bitrate": struct.unpack_from("<I", payload, 76)[0],
            }
        elif object_guid == ASF_STREAM_PROPERTIES:
            if len(payload) < 54:
                raise ValueError("Truncated ASF Stream Properties object")
            stream_type = payload[:16]
            type_data_length = struct.unpack_from("<I", payload, 40)[0]
            error_data_length = struct.unpack_from("<I", payload, 44)[0]
            stream_flags = struct.unpack_from("<H", payload, 48)[0]
            type_start = 54
            type_end = type_start + type_data_length
            if type_end + error_data_length > len(payload):
                raise ValueError("ASF stream type/error data exceeds its object")
            type_data = payload[type_start:type_end]
            stream_info = {"stream_number": stream_flags & 0x7F, "encrypted": bool(stream_flags & 0x8000)}
            if stream_type == ASF_VIDEO_MEDIA:
                if len(type_data) < 11:
                    raise ValueError("Truncated ASF video media data")
                width, height = struct.unpack_from("<II", type_data)
                format_size = struct.unpack_from("<H", type_data, 9)[0]
                bitmap = type_data[11 : 11 + format_size]
                if len(bitmap) < 20:
                    raise ValueError("Truncated ASF BITMAPINFOHEADER")
                stream_info.update(
                    {
                        "type": "video",
                        "width": width,
                        "height": height,
                        "bit_count": struct.unpack_from("<H", bitmap, 14)[0],
                        "codec": _fourcc(bitmap[16:20]),
                    }
                )
            elif stream_type == ASF_AUDIO_MEDIA:
                if len(type_data) < 16:
                    raise ValueError("Truncated ASF WAVEFORMATEX")
                stream_info.update(
                    {
                        "type": "audio",
                        "format_tag": struct.unpack_from("<H", type_data, 0)[0],
                        "channels": struct.unpack_from("<H", type_data, 2)[0],
                        "sample_rate": struct.unpack_from("<I", type_data, 4)[0],
                        "average_bytes_per_second": struct.unpack_from("<I", type_data, 8)[0],
                        "bits_per_sample": struct.unpack_from("<H", type_data, 14)[0],
                    }
                )
            else:
                stream_info.update({"type": "other", "media_guid": str(uuid.UUID(bytes_le=stream_type))})
            streams.append(stream_info)
        cursor += object_size
        parsed_objects += 1
    if parsed_objects != object_count or cursor != header_size:
        raise ValueError("ASF header object count/size mismatch")
    if file_properties is None:
        raise ValueError("ASF File Properties object not found")
    if not streams:
        raise ValueError("ASF Stream Properties object not found")
    if full_validation and file_properties["declared_file_size"] not in (0, file_size):
        raise ValueError(
            f"ASF declared file size mismatch: {file_properties['declared_file_size']} != {file_size}"
        )
    duration_seconds = max(
        0.0,
        file_properties["play_duration_100ns"] / 10_000_000
        - file_properties["preroll_ms"] / 1000,
    )
    return {
        "format": "ASF/WMV",
        "size_bytes": file_size,
        "header_size": header_size,
        "header_object_count": object_count,
        "duration_seconds": duration_seconds,
        "max_bitrate": file_properties["max_bitrate"],
        "packet_size": file_properties["max_packet_size"],
        "streams": streams,
        "full_validation": full_validation,
    }


def compare_asf_compatibility(original: dict, modified: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    original_streams = original["streams"]
    modified_streams = modified["streams"]
    if len(modified_streams) != len(original_streams):
        errors.append(
            f"stream count changed from {len(original_streams)} to {len(modified_streams)}"
        )
        return errors, warnings
    for index, (before, after) in enumerate(zip(original_streams, modified_streams), start=1):
        if before["type"] != after["type"]:
            errors.append(f"stream {index} type changed from {before['type']} to {after['type']}")
            continue
        if before["type"] == "video":
            for field, label in (("width", "width"), ("height", "height"), ("codec", "codec")):
                if before.get(field) != after.get(field):
                    errors.append(
                        f"video stream {index} {label} changed from {before.get(field)} to {after.get(field)}"
                    )
        elif before["type"] == "audio":
            for field, label in (
                ("format_tag", "codec tag"),
                ("channels", "channel count"),
                ("sample_rate", "sample rate"),
            ):
                if before.get(field) != after.get(field):
                    errors.append(
                        f"audio stream {index} {label} changed from {before.get(field)} to {after.get(field)}"
                    )
    if modified.get("duration_seconds") != original.get("duration_seconds"):
        warnings.append(
            f"duration changed from {original.get('duration_seconds'):.3f}s to "
            f"{modified.get('duration_seconds'):.3f}s"
        )
    return errors, warnings
