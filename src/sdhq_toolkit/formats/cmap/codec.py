from __future__ import annotations

import binascii
import colorsys
import json
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CMAP_HEADER_SIZE = 8
MAX_PIXELS = 100_000_000
COLOR_PNG_MARKER_KEY = "SDHQ-CMAP-Palette"
COLOR_PNG_MARKER_VALUE = "v1"


@dataclass(frozen=True, slots=True)
class CMapImage:
    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        _validate_dimensions(self.width, self.height)
        expected = self.width * self.height
        if len(self.pixels) != expected:
            raise ValueError(f"CMAP pixel count mismatch: expected {expected}, got {len(self.pixels)}")


def _validate_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")
    if width * height > MAX_PIXELS:
        raise ValueError(f"Image exceeds safety limit of {MAX_PIXELS} pixels")


def decode_cmap(data: bytes) -> CMapImage:
    if len(data) < CMAP_HEADER_SIZE:
        raise ValueError("CMAP file is shorter than its 8-byte header")
    width, height = struct.unpack_from("<II", data)
    _validate_dimensions(width, height)
    expected_size = CMAP_HEADER_SIZE + width * height
    if len(data) != expected_size:
        raise ValueError(f"Invalid CMAP size: expected {expected_size}, got {len(data)}")
    return CMapImage(width, height, data[CMAP_HEADER_SIZE:])


def encode_cmap(image: CMapImage) -> bytes:
    return struct.pack("<II", image.width, image.height) + image.pixels


def read_cmap(path: Path) -> CMapImage:
    return decode_cmap(path.read_bytes())


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind)
    checksum = binascii.crc32(payload, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def encode_png(image: CMapImage) -> bytes:
    rows = bytearray()
    for row in range(image.height):
        start = row * image.width
        rows.append(0)
        rows.extend(image.pixels[start : start + image.width])
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 0, 0, 0, 0)
    description = b"Description\x00School Days HQ CMAP; grayscale values are exact map bytes"
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"tEXt", description)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def cmap_palette() -> tuple[tuple[int, int, int], ...]:
    """Return a stable 256-color palette in which RGB maps uniquely to a CMAP ID."""
    colors = [(0, 0, 0)]
    for value in range(1, 256):
        hue = ((value * 0.618033988749895) % 1.0)
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.78, 1.0)
        colors.append((round(red * 255), round(green * 255), round(blue * 255)))
    if len(set(colors)) != 256:
        raise RuntimeError("Internal CMAP palette contains duplicate colors")
    return tuple(colors)


CMAP_PALETTE = cmap_palette()


def encode_colored_png(image: CMapImage) -> bytes:
    """Encode CMAP values as palette colors suitable for lossless visual editing."""
    rows = bytearray()
    for row in range(image.height):
        start = row * image.width
        rows.append(0)
        rows.extend(image.pixels[start : start + image.width])
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 3, 0, 0, 0)
    palette = b"".join(bytes(color) for color in CMAP_PALETTE)
    marker = COLOR_PNG_MARKER_KEY.encode("latin-1") + b"\x00" + COLOR_PNG_MARKER_VALUE.encode(
        "latin-1"
    )
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"PLTE", palette)
        + _png_chunk(b"tEXt", marker)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left


def _unfilter_scanlines(raw: bytes, width: int, height: int, channels: int) -> list[bytes]:
    stride = width * channels
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise ValueError(f"Invalid PNG data size: expected {expected}, got {len(raw)}")
    rows: list[bytes] = []
    cursor = 0
    previous = bytes(stride)
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = raw[cursor : cursor + stride]
        cursor += stride
        decoded = bytearray(stride)
        for index, value in enumerate(encoded):
            left = decoded[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                raise ValueError(f"Unsupported PNG filter type: {filter_type}")
            decoded[index] = (value + predictor) & 0xFF
        row = bytes(decoded)
        rows.append(row)
        previous = row
    return rows


def _parse_png(data: bytes) -> dict:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Input is not a PNG file")
    cursor = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    transparency: bytes | None = None
    compressed = bytearray()
    text_fields: dict[str, str] = {}
    saw_iend = False
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, cursor)[0]
        cursor += 4
        kind = data[cursor : cursor + 4]
        cursor += 4
        end = cursor + length
        if end + 4 > len(data):
            raise ValueError("Truncated PNG chunk payload")
        payload = data[cursor:end]
        cursor = end
        stored_crc = struct.unpack_from(">I", data, cursor)[0]
        cursor += 4
        calculated_crc = binascii.crc32(kind)
        calculated_crc = binascii.crc32(payload, calculated_crc) & 0xFFFFFFFF
        if stored_crc != calculated_crc:
            raise ValueError(f"PNG CRC mismatch in {kind.decode('ascii', errors='replace')}")
        if kind == b"IHDR":
            if ihdr is not None:
                raise ValueError("PNG contains multiple IHDR chunks")
            ihdr = payload
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"tEXt" and b"\x00" in payload:
            key, value = payload.split(b"\x00", 1)
            text_fields[key.decode("latin-1")] = value.decode("latin-1")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if payload:
                raise ValueError("PNG IEND chunk must be empty")
            saw_iend = True
            break
    if ihdr is None or len(ihdr) != 13 or not compressed or not saw_iend:
        raise ValueError("PNG is missing required IHDR, IDAT or IEND data")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    _validate_dimensions(width, height)
    if bit_depth != 8:
        raise ValueError("Only 8-bit PNG files are supported")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("Unsupported PNG compression, filter method or interlace mode")
    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise ValueError(f"Unsupported PNG color type: {color_type}")
    channels = channels_by_type[color_type]
    expected_raw_size = height * (width * channels + 1)
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(bytes(compressed), expected_raw_size + 1)
        if decompressor.unconsumed_tail or len(raw) > expected_raw_size:
            raise ValueError("PNG expands beyond its declared dimensions")
        raw += decompressor.flush()
        if len(raw) > expected_raw_size:
            raise ValueError("PNG expands beyond its declared dimensions")
    except zlib.error as exc:
        raise ValueError("Invalid PNG IDAT compression") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("Incomplete or trailing PNG IDAT compression")
    rows = _unfilter_scanlines(raw, width, height, channels)
    return {
        "width": width,
        "height": height,
        "color_type": color_type,
        "channels": channels,
        "palette": palette,
        "transparency": transparency,
        "text_fields": text_fields,
        "rows": rows,
    }


def decode_png_rgba(data: bytes) -> tuple[int, int, bytes]:
    """Decode an 8-bit, non-interlaced PNG into RGBA bytes for preview overlays."""
    parsed = _parse_png(data)
    width = parsed["width"]
    height = parsed["height"]
    color_type = parsed["color_type"]
    palette = parsed["palette"]
    transparency = parsed["transparency"]
    rgba = bytearray()
    if color_type == 3:
        if palette is None or len(palette) % 3 != 0 or len(palette) > 768:
            raise ValueError("Indexed PNG is missing a valid palette")
        colors = [tuple(palette[index : index + 3]) for index in range(0, len(palette), 3)]
        alpha_table = transparency or b""
        for row in parsed["rows"]:
            for palette_index in row:
                if palette_index >= len(colors):
                    raise ValueError("PNG pixel references an invalid palette index")
                rgba.extend(colors[palette_index])
                rgba.append(alpha_table[palette_index] if palette_index < len(alpha_table) else 255)
    else:
        transparent_gray = None
        transparent_rgb = None
        if transparency is not None:
            if color_type == 0 and len(transparency) == 2:
                transparent_gray = struct.unpack(">H", transparency)[0]
            elif color_type == 2 and len(transparency) == 6:
                transparent_rgb = struct.unpack(">HHH", transparency)
            else:
                raise ValueError("Invalid PNG transparency data")
        channels = parsed["channels"]
        for row in parsed["rows"]:
            for index in range(0, len(row), channels):
                if color_type == 0:
                    gray = row[index]
                    rgba.extend((gray, gray, gray, 0 if gray == transparent_gray else 255))
                elif color_type == 2:
                    red, green, blue = row[index : index + 3]
                    alpha = 0 if (red, green, blue) == transparent_rgb else 255
                    rgba.extend((red, green, blue, alpha))
                elif color_type == 4:
                    gray, alpha = row[index : index + 2]
                    rgba.extend((gray, gray, gray, alpha))
                else:
                    rgba.extend(row[index : index + 4])
    return width, height, bytes(rgba)


def encode_rgb_png(width: int, height: int, pixels: bytes, description: str) -> bytes:
    _validate_dimensions(width, height)
    if len(pixels) != width * height * 3:
        raise ValueError("RGB pixel count does not match image dimensions")
    rows = bytearray()
    stride = width * 3
    for row in range(height):
        start = row * stride
        rows.append(0)
        rows.extend(pixels[start : start + stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    text = b"Description\x00" + description.encode("latin-1", errors="replace")
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"tEXt", text)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def decode_png(data: bytes) -> CMapImage:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Input is not a PNG file")
    cursor = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    compressed = bytearray()
    saw_iend = False
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, cursor)[0]
        cursor += 4
        kind = data[cursor : cursor + 4]
        cursor += 4
        end = cursor + length
        if end + 4 > len(data):
            raise ValueError("Truncated PNG chunk payload")
        payload = data[cursor:end]
        cursor = end
        stored_crc = struct.unpack_from(">I", data, cursor)[0]
        cursor += 4
        calculated_crc = binascii.crc32(kind)
        calculated_crc = binascii.crc32(payload, calculated_crc) & 0xFFFFFFFF
        if stored_crc != calculated_crc:
            raise ValueError(f"PNG CRC mismatch in {kind.decode('ascii', errors='replace')}")
        if kind == b"IHDR":
            if ihdr is not None:
                raise ValueError("PNG contains multiple IHDR chunks")
            ihdr = payload
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"tRNS":
            raise ValueError("PNG transparency is ambiguous for CMAP import")
        elif kind == b"IEND":
            saw_iend = True
            break
    if ihdr is None or len(ihdr) != 13 or not compressed or not saw_iend:
        raise ValueError("PNG is missing required IHDR, IDAT or IEND data")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    _validate_dimensions(width, height)
    if bit_depth != 8:
        raise ValueError("Only 8-bit PNG files can be imported as CMAP")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("Unsupported PNG compression, filter method or interlace mode")
    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise ValueError(f"Unsupported PNG color type: {color_type}")
    channels = channels_by_type[color_type]
    expected_raw_size = height * (width * channels + 1)
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(bytes(compressed), expected_raw_size + 1)
        if decompressor.unconsumed_tail or len(raw) > expected_raw_size:
            raise ValueError("PNG expands beyond its declared dimensions")
        raw += decompressor.flush()
        if len(raw) > expected_raw_size:
            raise ValueError("PNG expands beyond its declared dimensions")
    except zlib.error as exc:
        raise ValueError("Invalid PNG IDAT compression") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("Incomplete or trailing PNG IDAT compression")
    rows = _unfilter_scanlines(raw, width, height, channels)
    pixels = bytearray()
    if color_type == 0:
        for row in rows:
            pixels.extend(row)
    elif color_type == 3:
        if palette is None or len(palette) % 3 != 0:
            raise ValueError("Indexed PNG is missing a valid palette")
        colors = [tuple(palette[index : index + 3]) for index in range(0, len(palette), 3)]
        for row in rows:
            for palette_index in row:
                if palette_index >= len(colors):
                    raise ValueError("PNG pixel references an invalid palette index")
                red, green, blue = colors[palette_index]
                if red != green or green != blue:
                    raise ValueError("Indexed PNG palette must contain only grayscale colors")
                pixels.append(red)
    else:
        for row in rows:
            for index in range(0, len(row), channels):
                if color_type == 4:
                    gray, alpha = row[index : index + 2]
                    if alpha != 255:
                        raise ValueError("PNG transparency is ambiguous for CMAP import")
                    pixels.append(gray)
                else:
                    red, green, blue = row[index : index + 3]
                    if red != green or green != blue:
                        raise ValueError("PNG must be grayscale before CMAP import")
                    if color_type == 6 and row[index + 3] != 255:
                        raise ValueError("PNG transparency is ambiguous for CMAP import")
                    pixels.append(red)
    return CMapImage(width, height, bytes(pixels))


def decode_colored_png(data: bytes, require_marker: bool = True) -> CMapImage:
    parsed = _parse_png(data)
    if require_marker and parsed["text_fields"].get(COLOR_PNG_MARKER_KEY) != COLOR_PNG_MARKER_VALUE:
        raise ValueError("PNG is missing the SDHQ CMAP palette marker")
    width, height, rgba = decode_png_rgba(data)
    reverse_palette = {color: value for value, color in enumerate(CMAP_PALETTE)}
    pixels = bytearray()
    for index in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[index : index + 4]
        if alpha != 255:
            raise ValueError("CMAP editing PNG must be fully opaque")
        color = (red, green, blue)
        if color not in reverse_palette:
            raise ValueError(
                f"Unknown CMAP palette color #{red:02X}{green:02X}{blue:02X} at pixel "
                f"{index // 4}"
            )
        pixels.append(reverse_palette[color])
    return CMapImage(width, height, bytes(pixels))


def _resize_rgba_nearest(
    source_width: int,
    source_height: int,
    pixels: bytes,
    target_width: int,
    target_height: int,
) -> bytes:
    if len(pixels) != source_width * source_height * 4:
        raise ValueError("RGBA pixel count does not match source dimensions")
    if source_width == target_width and source_height == target_height:
        return pixels
    resized = bytearray(target_width * target_height * 4)
    for target_y in range(target_height):
        source_y = min(source_height - 1, target_y * source_height // target_height)
        for target_x in range(target_width):
            source_x = min(source_width - 1, target_x * source_width // target_width)
            source_index = (source_y * source_width + source_x) * 4
            target_index = (target_y * target_width + target_x) * 4
            resized[target_index : target_index + 4] = pixels[source_index : source_index + 4]
    return bytes(resized)


def encode_overlay_png(image: CMapImage, background_png: bytes, opacity: float = 0.58) -> bytes:
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("Overlay opacity must be between 0 and 1")
    source_width, source_height, source_rgba = decode_png_rgba(background_png)
    background = _resize_rgba_nearest(
        source_width,
        source_height,
        source_rgba,
        image.width,
        image.height,
    )
    output = bytearray(image.width * image.height * 3)
    overlay_weight = round(opacity * 256)
    base_weight = 256 - overlay_weight
    for pixel_index, region in enumerate(image.pixels):
        rgba_index = pixel_index * 4
        rgb_index = pixel_index * 3
        alpha = background[rgba_index + 3]
        red = background[rgba_index]
        green = background[rgba_index + 1]
        blue = background[rgba_index + 2]
        if alpha != 255:
            red = (red * alpha + 32 * (255 - alpha) + 127) // 255
            green = (green * alpha + 32 * (255 - alpha) + 127) // 255
            blue = (blue * alpha + 32 * (255 - alpha) + 127) // 255
        if region == 0:
            output[rgb_index] = red
            output[rgb_index + 1] = green
            output[rgb_index + 2] = blue
        else:
            palette_red, palette_green, palette_blue = CMAP_PALETTE[region]
            output[rgb_index] = (
                red * base_weight + palette_red * overlay_weight + 128
            ) >> 8
            output[rgb_index + 1] = (
                green * base_weight + palette_green * overlay_weight + 128
            ) >> 8
            output[rgb_index + 2] = (
                blue * base_weight + palette_blue * overlay_weight + 128
            ) >> 8
    return encode_rgb_png(
        image.width,
        image.height,
        bytes(output),
        "School Days HQ CMAP region overlay; preview only",
    )


def _write_new(path: Path, data: bytes) -> None:
    path = path.resolve()
    if path.exists():
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def cmap_to_png(source: Path, output: Path) -> CMapImage:
    image = read_cmap(source)
    _write_new(output, encode_png(image))
    return image


def cmap_to_colored_png(source: Path, output: Path) -> CMapImage:
    image = read_cmap(source)
    _write_new(output, encode_colored_png(image))
    return image


def png_to_cmap(source: Path, output: Path) -> CMapImage:
    image = decode_png(source.read_bytes())
    _write_new(output, encode_cmap(image))
    return image


def colored_png_to_cmap(
    source: Path,
    output: Path,
    require_marker: bool = True,
) -> CMapImage:
    image = decode_colored_png(source.read_bytes(), require_marker=require_marker)
    _write_new(output, encode_cmap(image))
    return image


def cmap_overlay(source: Path, background: Path, output: Path, opacity: float = 0.58) -> CMapImage:
    image = read_cmap(source)
    _write_new(output, encode_overlay_png(image, background.read_bytes(), opacity=opacity))
    return image


def verify_cmap_directory(directory: Path, output: Path) -> dict:
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"CMAP directory not found: {directory}")
    files = sorted(
        (path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() == ".cmap"),
        key=lambda path: str(path).lower(),
    )
    if not files:
        raise FileNotFoundError(f"No CMAP files found in: {directory}")
    results = []
    aggregate_values: Counter[int] = Counter()
    for path in files:
        try:
            original = path.read_bytes()
            image = decode_cmap(original)
            rebuilt = encode_cmap(decode_png(encode_png(image)))
            status = "PASS" if rebuilt == original else "FAIL"
            values = Counter(image.pixels)
            aggregate_values.update(values)
            result = {
                "path": path.relative_to(directory).as_posix(),
                "width": image.width,
                "height": image.height,
                "size_bytes": len(original),
                "min_value": min(values),
                "max_value": max(values),
                "unique_value_count": len(values),
                "value_counts": [
                    {"value": value, "count": count}
                    for value, count in sorted(values.items())
                ],
                "status": status,
            }
        except (OSError, ValueError) as exc:
            result = {
                "path": path.relative_to(directory).as_posix(),
                "status": "FAIL",
                "error": str(exc),
            }
        results.append(result)
    failed = sum(item["status"] == "FAIL" for item in results)
    report = {
        "format": "School Days HQ CMAP round-trip",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "directory": str(directory),
        "file_count": len(files),
        "passed": len(files) - failed,
        "failed": failed,
        "status": "PASS" if failed == 0 else "FAIL",
        "aggregate_value_counts": [
            {"value": value, "count": count}
            for value, count in sorted(aggregate_values.items())
        ],
        "files": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
