import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from sdhq_toolkit.core.partial import extract_selection, restore_entry, load_metadata
from sdhq_toolkit.core.operations import CancellationToken, OperationCancelled
from sdhq_toolkit.core.batch import unpack_all
from sdhq_toolkit.formats.gpk.reader import GPKReader
from sdhq_toolkit.formats.gpk.writer import GPKWriter
from sdhq_toolkit.core import mods


KEY = b"synthetic-key-011"
FILES = {"INI/ONE.INI": b"[Settings]\r\nvalue=one\r\n", "INI/TWO.INI": b"[Settings]\r\nvalue=two\r\n", "DATA/RAW.BIN": b"raw-original-contents"}


def make_archive(path, files=None):
    files = files or FILES
    body, index = bytearray(b"MZ" + bytes(62)), bytearray()
    for name, content in files.items():
        packed = name.endswith(".INI")
        stored = zlib.compress(content) if packed else content
        header = stored[:4]
        encoded = name.encode("utf-16le")
        index.extend(struct.pack("<H", len(encoded) // 2) + encoded)
        index.extend(struct.pack("<ihIIiIB", 0, 0, len(body), len(stored), int.from_bytes(b"DFLT", "little") if packed else 0, len(content) if packed else 0, 4))
        index.extend(header)
        body.extend(stored[4:])
    index.extend(b"\0\0")
    encrypted = struct.pack("<I", len(index)) + zlib.compress(bytes(index))
    encrypted = bytes(value ^ KEY[i % len(KEY)] for i, value in enumerate(encrypted))
    path.write_bytes(body + encrypted + b"STKFile0PIDX" + struct.pack("<I", len(encrypted)) + b"STKFile0PACKFILE")


class PartialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "Test.gpk"
        make_archive(self.archive)
        self.destination = self.root / "workspace" / "Test"

    def test_partial_repack_preserves_all_unextracted_entries(self):
        metadata = extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        self.assertEqual([e["extracted"] for e in metadata["entries"]], [True, False, False])
        self.assertFalse(metadata["extraction_complete"])
        changed = b"[Settings]\r\nvalue=changed and longer\r\n"
        (self.destination / "INI/ONE.INI").write_bytes(changed)
        output = self.root / "rebuilt.gpk"
        report = GPKWriter(self.archive, KEY).repack(self.destination, output)
        self.assertEqual(report["modified_entries"], 1)
        verify = self.root / "verify"
        GPKReader(output, KEY).extract(verify)
        for name, content in FILES.items():
            self.assertEqual((verify / name).read_bytes(), changed if name == "INI/ONE.INI" else content)

    def test_zero_extracted_repack(self):
        extract_selection(self.archive, self.destination, KEY, [])
        output = self.root / "rebuilt.gpk"
        report = GPKWriter(self.archive, KEY).repack(self.destination, output)
        self.assertEqual(report["modified_entries"], 0)
        GPKReader(output, KEY).extract(self.root / "verify")
        self.assertEqual((self.root / "verify/DATA/RAW.BIN").read_bytes(), FILES["DATA/RAW.BIN"])

    def test_missing_extracted_is_error_not_reference_fallback(self):
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        (self.destination / "INI/ONE.INI").unlink()
        with self.assertRaises(FileNotFoundError):
            GPKWriter(self.archive, KEY).repack(self.destination, self.root / "out.gpk")
        self.assertFalse((self.root / "out.gpk.tmp").exists())

    def test_incremental_extraction_preserves_edits_and_restores_one(self):
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        (self.destination / "INI/ONE.INI").write_bytes(b"edited")
        metadata = extract_selection(self.archive, self.destination, KEY)
        self.assertTrue(metadata["extraction_complete"])
        self.assertEqual((self.destination / "INI/ONE.INI").read_bytes(), b"edited")
        restore_entry(self.archive, self.destination, KEY, "INI/ONE.INI")
        self.assertEqual((self.destination / "INI/ONE.INI").read_bytes(), FILES["INI/ONE.INI"])

    def test_cancel_extract_records_completed_entries_and_resumes(self):
        token = CancellationToken()
        def progress(*_):
            token.cancel()
        with self.assertRaises(OperationCancelled):
            extract_selection(self.archive, self.destination, KEY, cancel=token, progress=progress)
        metadata = load_metadata(self.destination)
        self.assertEqual([e["extracted"] for e in metadata["entries"]], [True, False, False])
        self.assertFalse(list(self.destination.rglob("*.sdhq-part")))
        self.assertTrue(extract_selection(self.archive, self.destination, KEY)["extraction_complete"])

    def test_cancel_repack_never_publishes_output(self):
        extract_selection(self.archive, self.destination, KEY, [])
        token = CancellationToken()
        with self.assertRaises(OperationCancelled):
            GPKWriter(self.archive, KEY).repack(self.destination, self.root / "out.gpk", cancel=token, progress=lambda *_: token.cancel())
        self.assertFalse((self.root / "out.gpk").exists())
        self.assertFalse((self.root / "out.gpk.tmp").exists())

    def test_invalid_selection_creates_nothing(self):
        with self.assertRaises(ValueError):
            extract_selection(self.archive, self.destination, KEY, ["../outside"])
        self.assertFalse(self.destination.exists())

    def test_unregistered_existing_file_is_not_silently_ignored(self):
        extract_selection(self.archive, self.destination, KEY, [])
        (self.destination / "INI").mkdir()
        (self.destination / "INI/ONE.INI").write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            GPKWriter(self.archive, KEY).repack(self.destination, self.root / "out.gpk")
        with self.assertRaises(FileExistsError):
            extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])

    def test_reference_mismatch_rejected(self):
        extract_selection(self.archive, self.destination, KEY, [])
        different = self.root / "different.gpk"
        make_archive(different, {"INI/OTHER.INI": b"other"})
        with self.assertRaises(ValueError):
            GPKWriter(different, KEY).repack(self.destination, self.root / "out.gpk")

    def test_legacy_metadata_remains_supported(self):
        GPKReader(self.archive, KEY).extract(self.destination)
        self.assertNotIn("extracted", load_metadata(self.destination)["entries"][0])
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        GPKWriter(self.archive, KEY).repack(self.destination, self.root / "out.gpk")

    def test_batch_completes_partial_workspace(self):
        packs = self.root / "packs"
        packs.mkdir()
        self.archive = self.archive.replace(packs / self.archive.name)
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        report = unpack_all(packs, self.destination.parent, KEY, self.root / "report.json", check_space=False)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(load_metadata(self.destination)["extraction_complete"])

    def test_partial_package_preview_build_apply_remove(self):
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        (self.destination / "INI/ONE.INI").write_bytes(b"[Settings]\r\nvalue=edited\r\n")
        project = self.root / "project"
        mods.create_mod_project(project, mod_id="test.partial", name="Partial", author="Test", version="1")
        _, preview = mods.build_mod_package(project, self.destination.parent, self.root / "output", preview_only=True)
        self.assertEqual([e["path"] for e in preview["files"]], ["INI/ONE.INI"])
        package, _ = mods.build_mod_package(project, self.destination.parent, self.root / "output", expected_files=preview["files"])
        target = self.root / "target" / "Test"
        extract_selection(self.archive, target, KEY, ["INI/ONE.INI"])
        mods.apply_mod_package(package, target.parent)
        mods.remove_mod_from_workspace("test.partial", target.parent)
        self.assertEqual((target / "INI/ONE.INI").read_bytes(), FILES["INI/ONE.INI"])
        self.assertFalse((target / "INI/TWO.INI").exists())

    def test_changed_preview_is_rejected(self):
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        file = self.destination / "INI/ONE.INI"
        file.write_bytes(b"edit one")
        project = self.root / "project"
        mods.create_mod_project(project, mod_id="test.preview", name="Test", author="Test", version="1")
        _, preview = mods.build_mod_package(project, self.destination.parent, self.root / "output", preview_only=True)
        file.write_bytes(b"edit two")
        with self.assertRaisesRegex(ValueError, "preview"):
            mods.build_mod_package(project, self.destination.parent, self.root / "output", expected_files=preview["files"])
        self.assertFalse((self.root / "output").exists())

    def test_cancel_package_copy_removes_temporary(self):
        extract_selection(self.archive, self.destination, KEY, ["INI/ONE.INI"])
        (self.destination / "INI/ONE.INI").write_bytes(b"modified")
        project = self.root / "project"
        mods.create_mod_project(project, mod_id="test.cancel", name="Test", author="Test", version="1")
        def progress(index, total, path):
            if path.startswith("files/"):
                raise OperationCancelled()
        with self.assertRaises(OperationCancelled):
            mods.build_mod_package(project, self.destination.parent, self.root / "output", progress=progress)
        self.assertEqual(list((self.root / "output").iterdir()), [])
