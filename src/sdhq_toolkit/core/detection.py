from __future__ import annotations

import struct


ASF_HEADER_OBJECT = bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")

SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"BM", "BMP"),
    (b"DDS ", "DDS"),
    (b"RIFF", "RIFF container (WAV/AVI/WebP)"),
    (b"OggS", "Ogg"),
    (b"ID3", "MP3 with ID3"),
    (b"PK\x03\x04", "ZIP"),
    (b"\x1f\x8b", "GZIP"),
    (b"MZ", "Windows executable"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
)


def detect_format(
    header: bytes,
    extension: str | None = None,
    file_size: int | None = None,
) -> str:
    normalized_extension = (extension or "").lower()
    if normalized_extension == ".ors" and header.lstrip().startswith(b"["):
        return "ORS script"
    if normalized_extension in {".ds_store", "[no extension]"} and header.startswith(b"\x00\x00\x00\x01Bud1"):
        return "macOS DS_Store"
    if header.startswith(ASF_HEADER_OBJECT):
        return "ASF/WMV"
    if normalized_extension == ".cmap" and len(header) >= 8:
        width, height = struct.unpack_from("<II", header)
        if width > 0 and height > 0 and width * height <= 100_000_000:
            if file_size is None or file_size == 8 + width * height:
                return "School Days CMAP"
    text_header = header.removeprefix(b"\xef\xbb\xbf")
    if normalized_extension == ".ini" and text_header.startswith(b"["):
        return "INI text"
    if normalized_extension == ".txt" and b"\x00" not in text_header:
        return "UTF-8 text"
    for signature, name in SIGNATURES:
        if header.startswith(signature):
            if name.startswith("RIFF") and len(header) >= 12:
                subtype = header[8:12]
                if subtype == b"WAVE":
                    return "WAV"
                if subtype == b"AVI ":
                    return "AVI"
                if subtype == b"WEBP":
                    return "WebP"
            return name
    return "UNKNOWN"
