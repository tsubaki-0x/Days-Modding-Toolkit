import struct
import unittest
import zlib

from sdhq_toolkit.formats.gpk.index import parse_decompressed_index, xor_with_repeating_key


class GPKIndexTests(unittest.TestCase):
    def test_repeating_xor_roundtrip(self):
        source = b"test encrypted index"
        key = b"1234"
        encrypted = xor_with_repeating_key(source, key)
        self.assertEqual(xor_with_repeating_key(encrypted, key), source)

    def test_parse_entry(self):
        name = "INI/Config.txt"
        encoded_name = name.encode("utf-16le")
        fixed = struct.pack("<ihIIiIB", 1, 2, 128, 50, 3, 100, 2)
        raw_index = struct.pack("<H", len(name)) + encoded_name + fixed + b"x\x9c" + b"\x00\x00"
        entries = parse_decompressed_index(raw_index, 1000)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].path, name)
        self.assertTrue(entries[0].is_packed)
        self.assertEqual(entries[0].header_hex, "789C")
        self.assertEqual(entries[0].compression_tag, "\x03\x00\x00\x00")

    def test_zlib_assumption(self):
        payload = b"index payload"
        compressed = zlib.compress(payload)
        self.assertEqual(zlib.decompress(compressed), payload)


if __name__ == "__main__":
    unittest.main()
