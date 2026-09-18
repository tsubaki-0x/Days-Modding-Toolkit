import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from sdhq_toolkit.core.folder_repack import FolderRepackService
from sdhq_toolkit.core.key_extractor import find_ciphercode
from sdhq_toolkit.formats.gpk.index import KNOWN_INDEX_KEYS, read_stack_index
from sdhq_toolkit.formats.gpk.reader import GPKReader
from sdhq_toolkit.formats.gpk.writer import GPKWriter


KEYS = dict(KNOWN_INDEX_KEYS)
SCHOOL = KEYS["SCHOOL_DAYS_HQ"]
SHINY = KEYS["SHINY_DAYS"]


def make_archive(path: Path, key: bytes, content: bytes = b"[Settings]\r\nvalue=one\r\n") -> None:
    name = "INI/TEST.INI"
    packed = zlib.compress(content, level=9)
    header_size = 4
    header = packed[:header_size]
    body = packed[header_size:]
    prefix = b"MZ" + bytes(62)
    raw_entry = (
        struct.pack("<H", len(name))
        + name.encode("utf-16le")
        + struct.pack(
            "<ihIIiIB",
            0,
            0,
            len(prefix),
            len(packed),
            int.from_bytes(b"DFLT", "little"),
            len(content),
            header_size,
        )
        + header
        + b"\x00\x00"
    )
    plain = struct.pack("<I", len(raw_entry)) + zlib.compress(raw_entry, level=9)
    encrypted = bytes(value ^ key[index % len(key)] for index, value in enumerate(plain))
    footer = (
        b"STKFile0PIDX"
        + struct.pack("<I", len(encrypted))
        + b"STKFile0PACKFILE"
    )
    path.write_bytes(prefix + body + encrypted + footer)


class MultiGameGPKTests(unittest.TestCase):
    def test_school_days_key_autodetection(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "School.gpk"
            make_archive(archive, SCHOOL)
            report = read_stack_index(archive)
            self.assertEqual(report["index_key_name"], "SCHOOL_DAYS_HQ")
            self.assertEqual(report["index_key_hex"], SCHOOL.hex().upper())
            self.assertEqual(report["entry_count"], 1)

    def test_shiny_days_key_autodetection(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "Shiny.gpk"
            make_archive(archive, SHINY)
            report = read_stack_index(archive)
            self.assertEqual(report["index_key_name"], "SHINY_DAYS")
            self.assertEqual(report["index_key_hex"], SHINY.hex().upper())
            self.assertEqual(report["entry_count"], 1)

    def test_wrong_supplied_key_falls_back_to_archive_variant(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "Shiny.gpk"
            make_archive(archive, SHINY)
            report = read_stack_index(archive, SCHOOL)
            self.assertEqual(report["index_key_name"], "SHINY_DAYS")

    def test_shiny_repack_preserves_shiny_pidx_key(self):
        original_content = b"[Settings]\r\nvalue=original\r\n"
        modified_content = b"[Settings]\r\nvalue=modified and longer\r\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "Shiny.gpk"
            make_archive(archive, SHINY, original_content)

            workspace = root / "workspace" / "Shiny"
            GPKReader(archive).extract(workspace)
            (workspace / "INI/TEST.INI").write_bytes(modified_content)

            output = root / "out.gpk"
            build = GPKWriter(archive).repack(workspace, output)
            self.assertEqual(build["index_key_name"], "SHINY_DAYS")

            rebuilt = read_stack_index(output)
            self.assertEqual(rebuilt["index_key_name"], "SHINY_DAYS")
            verify = root / "verify"
            GPKReader(output).extract(verify)
            self.assertEqual((verify / "INI/TEST.INI").read_bytes(), modified_content)

    def test_primary_folder_repack_works_without_game_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "Shiny.gpk"
            make_archive(archive, SHINY)
            edits = root / "edits"
            (edits / "INI").mkdir(parents=True)
            (edits / "INI/TEST.INI").write_bytes(
                b"[Settings]\r\nvalue=edited from shiny\r\n"
            )

            service = FolderRepackService(archive, edits)
            preview = service.preview()
            self.assertEqual(preview["metadata"]["index_key_name"], "SHINY_DAYS")

            result = service.build(root / "output")
            self.assertEqual(result["index_key_name"], "SHINY_DAYS")
            self.assertTrue(Path(result["output"]).is_file())

    def test_key_extractor_finds_known_shiny_literal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exe = root / "SHINYDAYS.exe"
            exe.write_bytes(b"MZ" + bytes(128) + SHINY + bytes(64))
            with patch(
                "sdhq_toolkit.core.key_extractor.read_named_resource",
                return_value=None,
            ):
                report = find_ciphercode(root)
            self.assertTrue(report["found"])
            self.assertEqual(report["source"], "literal_scan")
            self.assertEqual(report["key_name"], "SHINY_DAYS")
            self.assertEqual(bytes.fromhex(report["key_hex"]), SHINY)


if __name__ == "__main__":
    unittest.main()
