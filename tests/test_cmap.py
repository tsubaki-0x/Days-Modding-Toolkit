import binascii
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from sdhq_toolkit.formats.cmap.codec import (
    CMAP_PALETTE,
    CMapImage,
    PNG_SIGNATURE,
    decode_colored_png,
    cmap_to_png,
    decode_cmap,
    decode_png,
    decode_png_rgba,
    encode_cmap,
    encode_colored_png,
    encode_overlay_png,
    encode_png,
    encode_rgb_png,
    png_to_cmap,
    verify_cmap_directory,
)
from sdhq_toolkit.formats.cmap.project import build_cmap_project, export_cmap_project


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


class CMapTests(unittest.TestCase):
    def test_colored_palette_roundtrip_is_byte_identical(self):
        image = CMapImage(16, 16, bytes(range(256)))
        rebuilt = decode_colored_png(encode_colored_png(image))
        self.assertEqual(encode_cmap(rebuilt), encode_cmap(image))
        self.assertEqual(len(CMAP_PALETTE), len(set(CMAP_PALETTE)))

    def test_colored_import_requires_marker_and_known_colors(self):
        known_rgb = bytes(CMAP_PALETTE[7])
        without_marker = encode_rgb_png(1, 1, known_rgb, "marker removed by editor")
        with self.assertRaisesRegex(ValueError, "marker"):
            decode_colored_png(without_marker)
        self.assertEqual(decode_colored_png(without_marker, require_marker=False).pixels, b"\x07")

        unknown_rgb = encode_rgb_png(1, 1, b"\x01\x02\x03", "unknown color")
        with self.assertRaisesRegex(ValueError, "Unknown CMAP palette color"):
            decode_colored_png(unknown_rgb, require_marker=False)

    def test_overlay_resizes_background_without_changing_dimensions(self):
        image = CMapImage(4, 2, b"\x00\x01\x01\x00\x00\x02\x02\x00")
        background = encode_rgb_png(2, 2, b"\x80\x80\x80" * 4, "test")
        overlay = encode_overlay_png(image, background)
        width, height, rgba = decode_png_rgba(overlay)
        self.assertEqual((width, height), (4, 2))
        self.assertEqual(len(rgba), 4 * 2 * 4)
        self.assertEqual(rgba[:3], b"\x80\x80\x80")

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        rgba_png = (
            PNG_SIGNATURE
            + png_chunk(b"IHDR", ihdr)
            + png_chunk(b"IDAT", zlib.compress(b"\x00\x0a\x14\x1e\x80"))
            + png_chunk(b"IEND", b"")
        )
        self.assertEqual(decode_png_rgba(rgba_png), (1, 1, b"\x0a\x14\x1e\x80"))

    def test_project_export_and_modified_only_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "System"
            cmap_path = source / "TITLE/TITLE_WIDE.CMAP"
            cmap_path.parent.mkdir(parents=True)
            original_image = CMapImage(4, 2, b"\x00\x01\x01\x00\x00\x02\x02\x00")
            cmap_path.write_bytes(encode_cmap(original_image))
            (cmap_path.parent / "TITLE.PNG").write_bytes(
                encode_rgb_png(2, 2, b"\x80\x80\x80" * 4, "companion")
            )

            project = root / "cmap_project"
            manifest = export_cmap_project(source, project)
            self.assertEqual(manifest["file_count"], 1)
            self.assertEqual(manifest["overlays_created"], 1)
            self.assertEqual(manifest["used_region_ids"], [0, 1, 2])
            self.assertTrue(manifest["entries"][0]["companion_resized"])
            self.assertIn("ID 2", (project / "palette_legend.html").read_text())

            unchanged = build_cmap_project(project, root / "staged_unchanged")
            self.assertEqual(unchanged["status"], "PASS")
            self.assertEqual(unchanged["unchanged"], 1)
            self.assertEqual(unchanged["modified"], 0)

            editable = project / manifest["entries"][0]["editable_relative_path"]
            edited_image = decode_colored_png(editable.read_bytes())
            edited_pixels = bytearray(edited_image.pixels)
            edited_pixels[0] = 1
            editable.write_bytes(
                encode_colored_png(
                    CMapImage(edited_image.width, edited_image.height, bytes(edited_pixels))
                )
            )
            modified = build_cmap_project(project, root / "staged_modified")
            self.assertEqual(modified["status"], "PASS")
            self.assertEqual(modified["modified"], 1)
            rebuilt_path = root / "staged_modified/TITLE/TITLE_WIDE.CMAP"
            self.assertEqual(decode_cmap(rebuilt_path.read_bytes()).pixels[0], 1)
            self.assertFalse((root / "staged_modified/cmap_build_report.json").exists())
            self.assertTrue((root / "staged_modified.build.json").exists())

            edited_pixels[0] = 3
            editable.write_bytes(
                encode_colored_png(
                    CMapImage(edited_image.width, edited_image.height, bytes(edited_pixels))
                )
            )
            unsafe = build_cmap_project(project, root / "staged_new_id")
            self.assertEqual(unsafe["status"], "FAIL")
            self.assertIn("region IDs absent", unsafe["files"][0]["error"])

    def test_project_build_rejects_manifest_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "System"
            source.mkdir()
            (source / "TEST.CMAP").write_bytes(encode_cmap(CMapImage(1, 1, b"\x00")))
            project = root / "project"
            export_cmap_project(source, project)
            manifest_path = project / "cmap_project.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["source_relative_path"] = "../outside.CMAP"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = build_cmap_project(project, root / "staged")
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("Unsafe path", report["files"][0]["error"])

    def test_project_build_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "System"
            source.mkdir()
            cmap_path = source / "TEST.CMAP"
            cmap_path.write_bytes(encode_cmap(CMapImage(1, 1, b"\x00")))
            project = root / "project"
            export_cmap_project(source, project)
            cmap_path.write_bytes(encode_cmap(CMapImage(1, 1, b"\x01")))
            report = build_cmap_project(project, root / "staged")
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("changed after project export", report["files"][0]["error"])

    def test_cmap_png_cmap_is_byte_identical(self):
        image = CMapImage(4, 3, bytes(range(12)))
        original = encode_cmap(image)
        decoded = decode_png(encode_png(decode_cmap(original)))
        self.assertEqual(encode_cmap(decoded), original)

    def test_file_conversion_and_recursive_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "maps/UI/TEST.CMAP"
            source.parent.mkdir(parents=True)
            source.write_bytes(encode_cmap(CMapImage(3, 2, b"\x00\x01\x02\x03\x04\xff")))
            png = root / "editable/TEST.png"
            rebuilt = root / "rebuilt/TEST.CMAP"

            cmap_to_png(source, png)
            png_to_cmap(png, rebuilt)
            self.assertEqual(rebuilt.read_bytes(), source.read_bytes())

            report_path = root / "reports/cmap.json"
            report = verify_cmap_directory(root / "maps", report_path)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["passed"], 1)
            self.assertEqual(report["aggregate_value_counts"][-1]["value"], 255)
            self.assertEqual(json.loads(report_path.read_text())["file_count"], 1)

    def test_invalid_cmap_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid CMAP size"):
            decode_cmap(struct.pack("<II", 800, 600) + b"short")

    def test_png_filters_zero_through_four(self):
        width = 4
        pixels = bytes((10, 20, 30, 40))
        for filter_type in range(5):
            encoded = bytearray()
            for index, value in enumerate(pixels):
                left = pixels[index - 1] if index else 0
                if filter_type == 0 or filter_type == 2:
                    predictor = 0
                elif filter_type == 1:
                    predictor = left
                elif filter_type == 3:
                    predictor = left // 2
                else:
                    predictor = left
                encoded.append((value - predictor) & 0xFF)
            ihdr = struct.pack(">IIBBBBB", width, 1, 8, 0, 0, 0, 0)
            png = (
                PNG_SIGNATURE
                + png_chunk(b"IHDR", ihdr)
                + png_chunk(b"IDAT", zlib.compress(bytes([filter_type]) + bytes(encoded)))
                + png_chunk(b"IEND", b"")
            )
            self.assertEqual(decode_png(png).pixels, pixels)

    def test_colored_png_is_rejected(self):
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        png = (
            PNG_SIGNATURE
            + png_chunk(b"IHDR", ihdr)
            + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
            + png_chunk(b"IEND", b"")
        )
        with self.assertRaisesRegex(ValueError, "grayscale"):
            decode_png(png)


if __name__ == "__main__":
    unittest.main()
