import json
import struct
import tempfile
import unittest
from pathlib import Path

from sdhq_toolkit.core.asset_validation import (
    create_asset_baseline,
    validate_modified_assets,
)
from sdhq_toolkit.formats.assets.asf import (
    ASF_FILE_PROPERTIES,
    ASF_HEADER_OBJECT,
    ASF_STREAM_PROPERTIES,
    ASF_VIDEO_MEDIA,
    compare_asf_compatibility,
    inspect_asf,
)
from sdhq_toolkit.formats.assets.ogg import (
    compare_ogg_compatibility,
    inspect_ogg,
    ogg_crc,
)
from sdhq_toolkit.formats.assets.png import compare_png_compatibility, inspect_png
from sdhq_toolkit.formats.cmap.codec import encode_rgb_png
from sdhq_toolkit.utils.hashing import sha256_file


def make_vorbis_ogg(*, channels: int = 2, sample_rate: int = 44100) -> bytes:
    packet = (
        b"\x01vorbis"
        + struct.pack("<I", 0)
        + bytes([channels])
        + struct.pack("<I", sample_rate)
        + struct.pack("<iii", 192000, 128000, 64000)
        + b"\xb8\x01"
    )
    header = bytearray(27)
    header[:4] = b"OggS"
    header[4] = 0
    header[5] = 0x06
    struct.pack_into("<Q", header, 6, sample_rate * 2)
    struct.pack_into("<I", header, 14, 0x12345678)
    struct.pack_into("<I", header, 18, 0)
    header[26] = 1
    page = bytes(header) + bytes([len(packet)]) + packet
    checksum = ogg_crc(page)
    header[22:26] = struct.pack("<I", checksum)
    return bytes(header) + bytes([len(packet)]) + packet


def asf_object(guid: bytes, payload: bytes) -> bytes:
    return guid + struct.pack("<Q", 24 + len(payload)) + payload


def make_asf(*, width: int = 640, height: int = 480, codec: bytes = b"WMV3") -> bytes:
    bitmap = struct.pack(
        "<IiiHH4sIiiII",
        40,
        width,
        height,
        1,
        24,
        codec,
        width * height * 3,
        0,
        0,
        0,
        0,
    )
    type_data = struct.pack("<II", width, height) + b"\x00" + struct.pack("<H", len(bitmap)) + bitmap
    stream_payload = (
        ASF_VIDEO_MEDIA
        + bytes(16)
        + struct.pack("<QIIH", 0, len(type_data), 0, 1)
        + struct.pack("<I", 0)
        + type_data
    )
    stream_object = asf_object(ASF_STREAM_PROPERTIES, stream_payload)

    file_payload = bytearray(80)
    struct.pack_into("<Q", file_payload, 32, 1)
    struct.pack_into("<Q", file_payload, 40, 50_000_000)
    struct.pack_into("<Q", file_payload, 56, 0)
    struct.pack_into("<I", file_payload, 68, 4096)
    struct.pack_into("<I", file_payload, 72, 4096)
    struct.pack_into("<I", file_payload, 76, 2_000_000)
    file_object = asf_object(ASF_FILE_PROPERTIES, bytes(file_payload))

    total_size = 30 + len(file_object) + len(stream_object)
    struct.pack_into("<Q", file_payload, 16, total_size)
    file_object = asf_object(ASF_FILE_PROPERTIES, bytes(file_payload))
    return (
        ASF_HEADER_OBJECT
        + struct.pack("<QI", total_size, 2)
        + b"\x01\x02"
        + file_object
        + stream_object
    )


class AssetFormatTests(unittest.TestCase):
    def test_png_validation_and_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.png"
            modified_path = root / "modified.png"
            original_path.write_bytes(encode_rgb_png(2, 1, b"\x00\x00\x00\xff\xff\xff", "test"))
            modified_path.write_bytes(encode_rgb_png(2, 1, b"\xff\x00\x00\x00\xff\x00", "test"))
            original = inspect_png(original_path)
            modified = inspect_png(modified_path, full_validation=True)
            self.assertEqual(compare_png_compatibility(original, modified), ([], []))

            modified_path.write_bytes(encode_rgb_png(1, 1, b"\x00\x00\x00", "test"))
            changed = inspect_png(modified_path, full_validation=True)
            errors, _ = compare_png_compatibility(original, changed)
            self.assertIn("dimensions changed", errors[0])

    def test_ogg_crc_and_audio_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.ogg"
            modified_path = root / "modified.ogg"
            original_path.write_bytes(make_vorbis_ogg())
            modified_path.write_bytes(make_vorbis_ogg(channels=1))
            original = inspect_ogg(original_path, full_validation=True)
            modified = inspect_ogg(modified_path, full_validation=True)
            self.assertEqual(original["duration_seconds"], 2.0)
            errors, _ = compare_ogg_compatibility(original, modified)
            self.assertTrue(any("channel count changed" in error for error in errors))

            damaged = bytearray(original_path.read_bytes())
            damaged[-1] ^= 1
            original_path.write_bytes(damaged)
            with self.assertRaisesRegex(ValueError, "CRC mismatch"):
                inspect_ogg(original_path, full_validation=True)

    def test_asf_video_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.wmv"
            modified_path = root / "modified.wmv"
            original_path.write_bytes(make_asf())
            modified_path.write_bytes(make_asf(width=800))
            original = inspect_asf(original_path, full_validation=True)
            modified = inspect_asf(modified_path, full_validation=True)
            self.assertEqual(original["streams"][0]["codec"], "WMV3")
            errors, _ = compare_asf_compatibility(original, modified)
            self.assertTrue(any("width changed" in error for error in errors))


class AssetValidationTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> tuple[Path, Path]:
        workspace = root / "workspace"
        archive = workspace / "Test"
        (archive / ".sdhq").mkdir(parents=True)
        files = {
            "image.png": encode_rgb_png(2, 1, b"\x00\x00\x00\xff\xff\xff", "baseline"),
            "sound.ogg": make_vorbis_ogg(),
            "movie.wmv": make_asf(),
            "unknown.dat": b"unknown test payload",
        }
        entries = []
        for relative_path, data in files.items():
            path = archive / relative_path
            path.write_bytes(data)
            entries.append(
                {
                    "path": relative_path,
                    "extracted_sha256": sha256_file(path),
                }
            )
        metadata = {"format": "GPK/STACK", "entries": entries}
        (archive / ".sdhq/archive.json").write_text(json.dumps(metadata), encoding="utf-8")
        return workspace, archive

    def test_baseline_and_single_archive_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, archive = self.make_workspace(root)
            baseline_path = root / "baseline.json"
            baseline = create_asset_baseline(workspace, baseline_path)
            self.assertEqual(baseline["status"], "PASS")
            self.assertEqual(baseline["file_count"], 4)

            (archive / "image.png").write_bytes(
                encode_rgb_png(2, 1, b"\xff\x00\x00\x00\xff\x00", "modified")
            )
            report = validate_modified_assets(
                archive,
                baseline_path,
                root / "validation.json",
            )
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["modified"], 1)
            self.assertEqual(report["unchanged"], 3)

    def test_validation_blocks_incompatible_and_extra_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, archive = self.make_workspace(root)
            baseline_path = root / "baseline.json"
            create_asset_baseline(workspace, baseline_path)
            (archive / "image.png").write_bytes(encode_rgb_png(1, 1, b"\x00\x00\x00", "bad"))
            (archive / "extra.bin").write_bytes(b"extra")
            report = validate_modified_assets(workspace, baseline_path, root / "bad.json")
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["failed"], 2)
            self.assertEqual(report["extra"], 1)

    def test_unknown_modification_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, archive = self.make_workspace(root)
            baseline_path = root / "baseline.json"
            create_asset_baseline(workspace, baseline_path)
            (archive / "unknown.dat").write_bytes(b"modified unknown payload")
            blocked = validate_modified_assets(workspace, baseline_path, root / "blocked.json")
            self.assertEqual(blocked["status"], "FAIL")
            allowed = validate_modified_assets(
                workspace,
                baseline_path,
                root / "allowed.json",
                allow_unknown=True,
            )
            self.assertEqual(allowed["status"], "PASS")
            self.assertEqual(allowed["modified"], 1)

    def test_dirty_workspace_cannot_become_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace, archive = self.make_workspace(root)
            (archive / "image.png").write_bytes(b"not the extracted file")
            baseline = create_asset_baseline(workspace, root / "baseline.json")
            self.assertEqual(baseline["status"], "FAIL")
            self.assertEqual(baseline["failed"], 1)


if __name__ == "__main__":
    unittest.main()
