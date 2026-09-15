import tempfile
import unittest
from pathlib import Path

from sdhq_toolkit.core.inventory import scan_extracted, scan_packs, summarize_asset_inventory


class InventoryTests(unittest.TestCase):
    def test_scan_packs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Script.gpk").write_bytes(b"GPK sample")
            result = scan_packs(root)
            self.assertEqual(result["archive_count"], 1)
            self.assertEqual(result["archives"][0]["name"], "Script.gpk")

    def test_compact_summary_reclassifies_old_inventory(self):
        payload = {
            "generated_at_utc": "test",
            "extracted_directory": "workspace",
            "files": [
                {
                    "path": "Movie00/TEST.WMV",
                    "size_bytes": 16,
                    "extension": ".wmv",
                    "header_hex": "30 26 B2 75 8E 66 CF 11 A6 D9 00 AA 00 62 CE 6C",
                    "detected_format": "UNKNOWN",
                },
                {
                    "path": "System/TEST.CMAP",
                    "size_bytes": 12,
                    "extension": ".cmap",
                    "header_hex": "02 00 00 00 02 00 00 00 00 01 02 03",
                    "detected_format": "UNKNOWN",
                },
                {
                    "path": "System/FONTDATA.DAT",
                    "size_bytes": 4,
                    "extension": ".dat",
                    "header_hex": "00 00 04 00",
                    "detected_format": "UNKNOWN",
                },
            ],
        }
        summary = summarize_asset_inventory(payload)
        formats = {item["format"]: item["count"] for item in summary["detected_formats"]}
        self.assertEqual(formats["ASF/WMV"], 1)
        self.assertEqual(formats["School Days CMAP"], 1)
        self.assertEqual(summary["unknown_file_count"], 1)
        self.assertEqual(summary["unknown_files"][0]["path"], "System/FONTDATA.DAT")
    def test_scan_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "System" / "ui.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = scan_extracted(root)
            self.assertEqual(result["file_count"], 1)
            self.assertEqual(result["files"][0]["detected_format"], "PNG")


if __name__ == "__main__":
    unittest.main()
