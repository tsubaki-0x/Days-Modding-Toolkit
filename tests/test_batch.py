import json
import struct
import tempfile
import unittest
import zlib
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from sdhq_toolkit.core.batch import repack_all, unpack_all
from sdhq_toolkit.formats.gpk.reader import GPKReader


def create_synthetic_archive(path: Path, key: bytes, content: bytes) -> None:
    name = "DATA/TEST.BIN"
    compressed_entry = zlib.compress(content, level=9)
    header_size = 4
    entry_header = compressed_entry[:header_size]
    entry_body = compressed_entry[header_size:]
    prefix = b"MZ" + bytes(62)
    raw_entry = (
        struct.pack("<H", len(name))
        + name.encode("utf-16le")
        + struct.pack(
            "<ihIIiIB",
            0,
            0,
            len(prefix),
            len(compressed_entry),
            int.from_bytes(b"DFLT", "little"),
            len(content),
            header_size,
        )
        + entry_header
        + b"\x00\x00"
    )
    decrypted_index = struct.pack("<I", len(raw_entry)) + zlib.compress(raw_entry, level=9)
    encrypted_index = bytes(
        value ^ key[index % len(key)] for index, value in enumerate(decrypted_index)
    )
    footer = b"STKFile0PIDX" + struct.pack("<I", len(encrypted_index)) + b"STKFile0PACKFILE"
    path.write_bytes(prefix + entry_body + encrypted_index + footer)


class BatchTests(unittest.TestCase):
    def test_unpack_and_repack_all_are_resumable(self):
        key = b"0123456789ABCDEF"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packs = root / "packs"
            packs.mkdir()
            create_synthetic_archive(packs / "Alpha.GPK", key, b"alpha" * 1000)
            create_synthetic_archive(packs / "Beta.gpk", key, b"beta" * 1000)
            workspace = root / "workspace"

            first = unpack_all(
                packs,
                workspace,
                key,
                root / "reports" / "unpack.json",
                check_space=False,
            )
            self.assertEqual(first["status"], "PASS")
            self.assertEqual(first["passed_archives"], 2)
            self.assertEqual((workspace / "Alpha/DATA/TEST.BIN").read_bytes(), b"alpha" * 1000)

            resumed = unpack_all(
                packs,
                workspace,
                key,
                root / "reports" / "unpack-resumed.json",
                check_space=False,
            )
            self.assertEqual(resumed["skipped_archives"], 2)
            self.assertEqual(resumed["passed_archives"], 0)

            (workspace / "Alpha/DATA/TEST.BIN").write_bytes(b"modified" * 1000)
            output = root / "output"
            rebuilt = repack_all(
                workspace,
                packs,
                output,
                key,
                root / "reports" / "repack.json",
                check_space=False,
            )
            self.assertEqual(rebuilt["status"], "PASS")
            self.assertEqual(rebuilt["passed_archives"], 2)
            verify = root / "verify" / "Alpha"
            GPKReader(output / "Alpha.gpk", key).extract(verify, chunk_size=7)
            self.assertEqual((verify / "DATA/TEST.BIN").read_bytes(), b"modified" * 1000)

            resumed_repack = repack_all(
                workspace,
                packs,
                output,
                key,
                root / "reports" / "repack-resumed.json",
                check_space=False,
            )
            self.assertEqual(resumed_repack["skipped_archives"], 2)

            (workspace / "Beta/DATA/TEST.BIN").write_bytes(b"new beta state")
            changed_after_build = repack_all(
                workspace,
                packs,
                output,
                key,
                root / "reports" / "repack-changed.json",
                check_space=False,
            )
            self.assertEqual(changed_after_build["status"], "PARTIAL")
            self.assertEqual(changed_after_build["skipped_archives"], 1)
            self.assertEqual(changed_after_build["failed_archives"], 1)

    def test_unpack_all_stops_before_writing_when_space_is_insufficient(self):
        key = b"0123456789ABCDEF"
        DiskUsage = namedtuple("DiskUsage", "total used free")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packs = root / "packs"
            packs.mkdir()
            create_synthetic_archive(packs / "Alpha.GPK", key, b"content")
            workspace = root / "workspace"
            report_path = root / "reports" / "unpack.json"

            with patch(
                "sdhq_toolkit.core.batch.shutil.disk_usage",
                return_value=DiskUsage(total=1, used=1, free=0),
            ):
                report = unpack_all(packs, workspace, key, report_path)

            self.assertEqual(report["status"], "INSUFFICIENT_SPACE")
            self.assertFalse((workspace / "Alpha").exists())
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(saved["space_check"]["passed"])


if __name__ == "__main__":
    unittest.main()
