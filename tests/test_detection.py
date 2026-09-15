import unittest

from sdhq_toolkit.core.detection import detect_format


class DetectionTests(unittest.TestCase):
    def test_png(self):
        self.assertEqual(detect_format(b"\x89PNG\r\n\x1a\nrest"), "PNG")

    def test_wave(self):
        self.assertEqual(detect_format(b"RIFF\x00\x00\x00\x00WAVE"), "WAV")

    def test_unknown(self):
        self.assertEqual(detect_format(b"SDHQ"), "UNKNOWN")

    def test_ors_script(self):
        self.assertEqual(detect_format(b"[SkipFRAME]=00:01:02;", ".ors"), "ORS script")

    def test_ds_store(self):
        self.assertEqual(detect_format(b"\x00\x00\x00\x01Bud1", "[no extension]"), "macOS DS_Store")

    def test_asf_wmv(self):
        header = bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")
        self.assertEqual(detect_format(header, ".wmv"), "ASF/WMV")

    def test_cmap_with_exact_dimensions(self):
        header = b"\x20\x03\x00\x00\x58\x02\x00\x00" + bytes(24)
        self.assertEqual(detect_format(header, ".cmap", 480008), "School Days CMAP")
        self.assertEqual(detect_format(header, ".cmap", 480009), "UNKNOWN")

    def test_ini_and_text(self):
        self.assertEqual(detect_format(b"[Version]=\"1\"", ".ini"), "INI text")
        self.assertEqual(detect_format(b"\xef\xbb\xbfFileName = {", ".txt"), "UTF-8 text")


if __name__ == "__main__":
    unittest.main()
