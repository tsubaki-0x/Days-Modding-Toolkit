from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path

from ..cmap.codec import MAX_PIXELS, PNG_SIGNATURE


COLOR_TYPES = {
    0: "grayscale",
    2: "RGB",
    3: "indexed",
    4: "grayscale-alpha",
    6: "RGBA",
}

ALLOWED_BIT_DEPTHS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}

CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _scanline_sizes(width: int, height: int, bit_depth: int, color_type: int, interlace: int) -> list[int]:
    channels = CHANNELS[color_type]

    def pass_sizes(pass_width: int, pass_height: int) -> list[int]:
        if pass_width <= 0 or pass_height <= 0:
            return []
        row_bytes = (pass_width * channels * bit_depth + 7) // 8
        return [row_bytes] * pass_height

    if interlace == 0:
        return pass_sizes(width, height)
    sizes: list[int] = []
    for x_start, y_start, x_step, y_step in (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    ):
        pass_width = (width - x_start + x_step - 1) // x_step if width > x_start else 0
        pass_height = (height - y_start + y_step - 1) // y_step if height > y_start else 0
        sizes.extend(pass_sizes(pass_width, pass_height))
    return sizes


def _validate_complete_png(
    data: bytes,
    *,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> None:
    cursor = 8
    compressed = bytearray()
    saw_idat = False
    saw_iend = False
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        payload_start = cursor + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError("Truncated PNG chunk payload")
        payload = data[payload_start:payload_end]
        stored_crc = struct.unpack_from(">I", data, payload_end)[0]
        calculated_crc = binascii.crc32(kind)
        calculated_crc = binascii.crc32(payload, calculated_crc) & 0xFFFFFFFF
        if stored_crc != calculated_crc:
            raise ValueError(f"PNG CRC mismatch in {kind.decode('ascii', errors='replace')}")
        if kind == b"IDAT":
            saw_idat = True
            compressed.extend(payload)
        elif kind == b"IEND":
            if payload:
                raise ValueError("PNG IEND chunk must be empty")
            saw_iend = True
            cursor = crc_end
            break
        cursor = crc_end
    if not saw_idat or not saw_iend or cursor != len(data):
        raise ValueError("PNG is missing IDAT/IEND data or has trailing bytes")

    row_sizes = _scanline_sizes(width, height, bit_depth, color_type, interlace)
    expected_size = sum(row_size + 1 for row_size in row_sizes)
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(bytes(compressed), expected_size + 1)
        if decompressor.unconsumed_tail or len(raw) > expected_size:
            raise ValueError("PNG expands beyond its declared dimensions")
        raw += decompressor.flush()
    except zlib.error as exc:
        raise ValueError("Invalid PNG IDAT compression") from exc
    if len(raw) != expected_size or not decompressor.eof or decompressor.unused_data:
        raise ValueError("PNG decompressed data size is invalid")
    row_cursor = 0
    for row_size in row_sizes:
        if raw[row_cursor] > 4:
            raise ValueError(f"Unsupported PNG filter type: {raw[row_cursor]}")
        row_cursor += row_size + 1


def inspect_png(path: Path, *, full_validation: bool = False) -> dict:
    size = path.stat().st_size
    with path.open("rb") as stream:
        prefix = stream.read(33)
    if len(prefix) != 33 or prefix[:8] != PNG_SIGNATURE:
        raise ValueError("Invalid or truncated PNG signature/IHDR")
    length = struct.unpack_from(">I", prefix, 8)[0]
    if length != 13 or prefix[12:16] != b"IHDR":
        raise ValueError("PNG does not begin with a valid IHDR chunk")
    payload = prefix[16:29]
    stored_crc = struct.unpack_from(">I", prefix, 29)[0]
    calculated_crc = binascii.crc32(b"IHDR")
    calculated_crc = binascii.crc32(payload, calculated_crc) & 0xFFFFFFFF
    if stored_crc != calculated_crc:
        raise ValueError("PNG IHDR CRC mismatch")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", payload
    )
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid PNG dimensions: {width}x{height}")
    if width * height > MAX_PIXELS:
        raise ValueError(f"PNG exceeds safety limit of {MAX_PIXELS} pixels")
    if color_type not in COLOR_TYPES:
        raise ValueError(f"Unsupported PNG color type: {color_type}")
    if bit_depth not in ALLOWED_BIT_DEPTHS[color_type]:
        raise ValueError(f"Invalid PNG bit depth {bit_depth} for color type {color_type}")
    if compression != 0 or filtering != 0:
        raise ValueError("Unsupported PNG compression or filter method")
    if interlace not in (0, 1):
        raise ValueError(f"Invalid PNG interlace method: {interlace}")
    if full_validation:
        data = path.read_bytes()
        _validate_complete_png(
            data,
            width=width,
            height=height,
            bit_depth=bit_depth,
            color_type=color_type,
            interlace=interlace,
        )
    return {
        "format": "PNG",
        "size_bytes": size,
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "color_model": COLOR_TYPES[color_type],
        "compression_method": compression,
        "filter_method": filtering,
        "interlace_method": interlace,
        "full_validation": full_validation,
    }


def compare_png_compatibility(original: dict, modified: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if (modified["width"], modified["height"]) != (original["width"], original["height"]):
        errors.append(
            f"dimensions changed from {original['width']}x{original['height']} to "
            f"{modified['width']}x{modified['height']}"
        )
    if modified["bit_depth"] != original["bit_depth"]:
        errors.append(
            f"bit depth changed from {original['bit_depth']} to {modified['bit_depth']}"
        )
    if modified["interlace_method"] != original["interlace_method"]:
        errors.append(
            f"interlace mode changed from {original['interlace_method']} to "
            f"{modified['interlace_method']}"
        )
    original_type = original["color_type"]
    modified_type = modified["color_type"]
    compatible_pairs = ({2, 6}, {0, 4})
    if modified_type != original_type:
        if any({original_type, modified_type}.issubset(pair) for pair in compatible_pairs):
            warnings.append(
                f"color model changed from {original['color_model']} to {modified['color_model']}"
            )
        else:
            errors.append(
                f"color model changed from {original['color_model']} to {modified['color_model']}"
            )
    return errors, warnings
