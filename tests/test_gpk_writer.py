import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from sdhq_toolkit.formats.gpk.reader import GPKReader
from sdhq_toolkit.formats.gpk.writer import GPKWriter


def create_synthetic_archive(path: Path, key: bytes, content: bytes) -> None:
    name = "INI/TEST.INI"
    compressed_entry = zlib.compress(content, level=9)
    header_size = 4
    entry_header = compressed_entry[:header_size]
    entry_body = compressed_entry[header_size:]
    prefix = b"MZ" + bytes(62)
    entry_offset = len(prefix)
    raw_entry = (
        struct.pack("<H", len(name))
        + name.encode("utf-16le")
        + struct.pack(
            "<ihIIiIB",
            0,
            0,
            entry_offset,
            len(compressed_entry),
            int.from_bytes(b"DFLT", "little"),
            len(content),
            header_size,
        )
        + entry_header
        + b"\x00\x00"
    )
    index_prefix = struct.pack("<I", len(raw_entry))
    decrypted_index = index_prefix + zlib.compress(raw_entry, level=9)
    encrypted_index = bytes(value ^ key[index % len(key)] for index, value in enumerate(decrypted_index))
    footer = b"STKFile0PIDX" + struct.pack("<I", len(encrypted_index)) + b"STKFile0PACKFILE"
    path.write_bytes(prefix + entry_body + encrypted_index + footer)


class GPKWriterTests(unittest.TestCase):
    def test_reference_repack_unchanged_and_modified(self):
        key = b"0123456789ABCDEF"
        original_content = b"value=original\r\n"
        modified_content = b"value=modified and longer\r\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "Ini.GPK"
            create_synthetic_archive(original, key, original_content)
            workspace = root / "workspace" / "Ini"
            GPKReader(original, key).extract(workspace)

            unchanged = root / "output" / "Ini.gpk"
            report = GPKWriter(original, key).repack(workspace, unchanged, chunk_size=5)
            self.assertEqual(report["modified_entries"], 0)
            self.assertTrue(report["streaming"])
            unchanged_extract = root / "verify" / "unchanged"
            GPKReader(unchanged, key).extract(unchanged_extract)
            self.assertEqual((unchanged_extract / "INI/TEST.INI").read_bytes(), original_content)

            (workspace / "INI/TEST.INI").write_bytes(modified_content)
            modified = root / "output" / "Ini-modified.gpk"
            report = GPKWriter(original, key).repack(workspace, modified, chunk_size=5)
            self.assertEqual(report["modified_entries"], 1)
            modified_extract = root / "verify" / "modified"
            GPKReader(modified, key).extract(modified_extract)
            self.assertEqual((modified_extract / "INI/TEST.INI").read_bytes(), modified_content)


if __name__ == "__main__":
    unittest.main()
