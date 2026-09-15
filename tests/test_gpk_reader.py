import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from sdhq_toolkit.formats.gpk.reader import GPKReader


class GPKReaderTests(unittest.TestCase):
    def test_extract_synthetic_stack_archive(self):
        key = b"0123456789ABCDEF"
        name = "INI/TEST.INI"
        content = b"value=confirmed\r\n"
        compressed_entry = zlib.compress(content, level=9)
        header_size = 4
        entry_header = compressed_entry[:header_size]
        entry_body = compressed_entry[header_size:]
        prefix = b"MZ" + bytes(62)
        entry_offset = len(prefix)
        stored_size = len(compressed_entry)

        raw_entry = (
            struct.pack("<H", len(name))
            + name.encode("utf-16le")
            + struct.pack(
                "<ihIIiIB",
                0,
                0,
                entry_offset,
                stored_size,
                int.from_bytes(b"DFLT", "little"),
                len(content),
                header_size,
            )
            + entry_header
            + b"\x00\x00"
        )
        decrypted_index = struct.pack("<I", len(raw_entry)) + zlib.compress(raw_entry)
        encrypted_index = bytes(
            value ^ key[index % len(key)] for index, value in enumerate(decrypted_index)
        )
        footer = b"STKFile0PIDX" + struct.pack("<I", len(encrypted_index)) + b"STKFile0PACKFILE"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "Ini.GPK"
            archive.write_bytes(prefix + entry_body + encrypted_index + footer)
            destination = root / "workspace" / "Ini"
            metadata = GPKReader(archive, key).extract(destination, chunk_size=3)

            self.assertEqual((destination / name).read_bytes(), content)
            self.assertEqual(metadata["entry_count"], 1)
            self.assertTrue(metadata["streaming"])
            saved = json.loads((destination / ".sdhq" / "archive.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["entries"][0]["compression_tag"], "DFLT")


if __name__ == "__main__":
    unittest.main()
