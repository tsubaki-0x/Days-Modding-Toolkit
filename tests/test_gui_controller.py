import tempfile
import struct
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from sdhq_toolkit.core.desktop import DesktopService, Settings
from sdhq_toolkit.core.operations import CancellationToken, OperationCancelled
from sdhq_toolkit.gui.controller import JobController, filter_rows, resolve_selection
from sdhq_toolkit.core import mods
from test_partial import make_archive, KEY, FILES
from sdhq_toolkit.formats.cmap.codec import encode_rgb_png
from sdhq_toolkit.formats.gpk.reader import GPKReader


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packs = self.root / "Packs"
        self.packs.mkdir()
        make_archive(self.packs / "Test.gpk")
        self.service = DesktopService(Settings(self.root, self.packs, self.root / "workspace", self.root / "reports", self.root / "output"), KEY)
        self.kw = dict(cancel=CancellationToken(), progress=lambda *_: None)

    def test_index_browsing_and_filters_without_extraction(self):
        rows = self.service.detect(**self.kw)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["state"] == "não extraído" for r in rows))
        self.assertFalse(self.service.settings.workspace.exists())
        filtered = filter_rows(rows, query="test one", extension=".ini", format_name="INI", state="não extraído")
        self.assertEqual([r["path"] for r in filtered], ["INI/ONE.INI"])
        self.assertEqual(len(filter_rows(rows, scope=[("Test", "INI")])), 2)

    def test_validation_failure_is_reported_as_failure_not_job_success(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)
        self.service.file_path("Test", "INI/ONE.INI").write_bytes(b"[Changed]\r\nnew_key=123\r\n")
        jobs = JobController()
        jobs.start("Atualizar e validar", self.service.validate, self.root / "reports")
        jobs.thread.join(5)
        event = jobs.events.get_nowait()
        self.assertEqual(event[2], "FAIL")
        self.assertEqual(event[3]["status"], "FAIL")
        self.assertFalse(event[3]["can_repack"])
        self.assertEqual(event[3]["invalid"], 1)

    def test_experimental_repack_preserves_malformed_and_unknown_edited_bytes(self):
        original = {
            "DATA/MAP.CMAP": struct.pack("<II", 2, 1) + bytes([1, 2]),
            "DATA/IMAGE.PNG": encode_rgb_png(2, 1, bytes(6), "original"),
            "DATA/FONT.DAT": b"original font bytes",
        }
        archive = self.packs / "Test.gpk"
        make_archive(archive, original)
        original_archive = archive.read_bytes()
        self.service.detect(**self.kw)
        self.service.extract({"Test": None}, **self.kw)
        edited = {name: data + b"edited trailing bytes" for name, data in original.items()}
        for name, data in edited.items():
            self.service.file_path("Test", name).write_bytes(data)
        strict = self.service.validate(names=["Test"], **self.kw)
        self.assertEqual(strict["status"], "FAIL")
        self.assertEqual(strict["invalid"], 2)
        self.assertEqual(strict["blocking_count"], 3)
        experimental = self.service.validate(names=["Test"], compatibility_mode="experimental", **self.kw)
        self.assertEqual(experimental["status"], "WARN")
        self.assertTrue(experimental["can_repack"])
        result = self.service.repack({"Test": None}, compatibility_mode="experimental", **self.kw)[0]
        self.assertEqual(result["validation"], "PASS")
        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["asset_validation"]["invalid"], 2)
        destination = self.root / "verify-experimental"
        GPKReader(Path(result["output"]), KEY).extract(destination)
        for name, data in edited.items():
            self.assertEqual((destination / name).read_bytes(), data)
        self.assertEqual(archive.read_bytes(), original_archive)

    def test_experimental_mode_does_not_allow_missing_or_new_entries(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": None}, **self.kw)
        self.service.file_path("Test", "INI/ONE.INI").unlink()
        self.service.file_path("Test", "INI/RENAMED.INI").write_bytes(b"renamed")
        result = self.service.validate(compatibility_mode="experimental", **self.kw)
        self.assertFalse(result["can_repack"])
        self.assertEqual(result["blocking_count"], 2)
        self.assertTrue(all(item["category"] == "container" for item in result["errors"]))
        with self.assertRaises(ValueError):
            self.service.repack({"Test": None}, compatibility_mode="experimental", **self.kw)
        self.assertFalse(self.service.settings.output.exists())

    def test_valid_png_and_text_may_change_size_in_strict_mode(self):
        originals = {
            "DATA/IMAGE.PNG": encode_rgb_png(2, 1, bytes(6), "original"),
            "INI/ONE.INI": FILES["INI/ONE.INI"],
        }
        make_archive(self.packs / "Test.gpk", originals)
        self.service.detect(**self.kw)
        self.service.extract({"Test": None}, **self.kw)
        edited = {
            "DATA/IMAGE.PNG": encode_rgb_png(2, 1, b"\xff\0\0\0\xff\0", "longer valid comment " * 40),
            "INI/ONE.INI": b"[Settings]\r\nvalue=a considerably longer edited value\r\n",
        }
        for name, data in edited.items():
            self.assertNotEqual(len(originals[name]), len(data))
            self.service.file_path("Test", name).write_bytes(data)
        validation = self.service.validate(**self.kw)
        self.assertEqual(validation["status"], "PASS")
        self.assertEqual(validation["modified"], 2)
        result = self.service.repack({"Test": None}, **self.kw)[0]
        destination = self.root / "verify-valid"
        GPKReader(Path(result["output"]), KEY).extract(destination)
        for name, data in edited.items():
            self.assertEqual((destination / name).read_bytes(), data)

    def test_repeated_repack_preserves_previous_output(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": None}, **self.kw)
        first = Path(self.service.repack({"Test": None}, **self.kw)[0]["output"])
        first_content = first.read_bytes()
        edited = b"[Settings]\r\nvalue=second build\r\n"
        self.service.file_path("Test", "INI/ONE.INI").write_bytes(edited)
        second = Path(self.service.repack({"Test": None}, **self.kw)[0]["output"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), first_content)
        self.assertEqual(second.parent.parent, self.service.settings.output)
        destination = self.root / "verify-second"
        GPKReader(second, KEY).extract(destination)
        self.assertEqual((destination / "INI/ONE.INI").read_bytes(), edited)

    def test_files_folder_archive_all_and_deduplication(self):
        rows = self.service.detect(**self.kw)
        selection = resolve_selection(rows, files=[("Test", "INI/ONE.INI")], folders=[("Test", "INI")])
        self.assertEqual(selection, {"Test": ["INI/ONE.INI", "INI/TWO.INI"]})
        self.assertEqual(len(resolve_selection(rows, folders=[("Test", "")])["Test"]), 3)
        self.assertEqual(len(resolve_selection(rows, all_files=True)["Test"]), 3)
        self.assertFalse(resolve_selection(rows))

    def test_detect_existing_workspace_skips_content_validation(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)
        self.service.file_path("Test", "INI/ONE.INI").write_bytes(b"external edit")
        with patch.object(self.service, "refresh", side_effect=AssertionError("must not scan assets")), \
             patch("sdhq_toolkit.core.desktop.sha256_file", side_effect=AssertionError("must not hash assets")):
            rows = self.service.detect(**self.kw)
        self.assertEqual(rows[0]["state"], "não verificado")
        self.assertEqual(rows[1]["state"], "não extraído")
        self.assertNotIn("sha256", rows[0])
        self.assertEqual(self.service.refresh(**self.kw)[0]["state"], "inválido")

    def test_extract_reports_existing_files_and_does_not_validate_workspace(self):
        self.service.detect(**self.kw)
        with patch.object(self.service, "refresh", side_effect=AssertionError("no implicit validation")):
            first = self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)[0]
            self.assertEqual(first["newly_extracted"], 1)
            self.assertEqual(first["already_extracted"], 0)
            self.assertEqual(self.service.rows[0]["state"], "original")
            self.service.file_path("Test", "INI/ONE.INI").write_bytes(b"external edit")
            second = self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)[0]
            self.assertEqual(second["newly_extracted"], 0)
            self.assertEqual(second["already_extracted"], 1)
            self.assertEqual(self.service.file_path("Test", "INI/ONE.INI").read_bytes(), b"external edit")

    def test_validation_and_repack_skip_unselected_archives(self):
        make_archive(self.packs / "Other.gpk")
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"], "Other": ["INI/ONE.INI"]}, **self.kw)
        self.service.file_path("Other", "INI/ONE.INI").unlink()
        self.service.catalog(**self.kw)
        result = self.service.repack({"Test": []}, **self.kw)
        self.assertEqual(len(result), 1)
        self.assertTrue((self.service.settings.output / "Test.gpk").is_file())
        other = next(row for row in self.service.rows if row["archive"] == "Other")
        self.assertEqual(other["state"], "não verificado")
        rows = self.service.refresh(names=["Other"], **self.kw)
        self.assertEqual(next(row for row in rows if row["archive"] == "Other")["state"], "ausente")

    def test_reference_cache_reloads_after_replacement_and_new_extraction(self):
        self.service.detect(**self.kw)
        old_size = self.service.indexes["Test"]["archive_size"]
        replacement = dict(FILES)
        replacement["DATA/RAW.BIN"] = b"new reference, a different archive body" * 4
        make_archive(self.packs / "Test.gpk", replacement)
        self.service.extract({"Test": None}, **self.kw)
        rows = self.service.refresh(names=["Test"], **self.kw)
        self.assertNotEqual(old_size, self.service.indexes["Test"]["archive_size"])
        self.assertTrue(all(row["state"] == "original" for row in rows))
        details = self.service.inspect("Test", "DATA/RAW.BIN", cancel=self.kw["cancel"])
        self.assertEqual(details["original"]["size_bytes"], len(replacement["DATA/RAW.BIN"]))

    def test_reference_replacement_keeps_real_metadata_mismatch_blocked(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": None}, **self.kw)
        replacement = dict(FILES)
        replacement["DATA/RAW.BIN"] = b"a longer reference body" * 10
        make_archive(self.packs / "Test.gpk", replacement)
        with self.assertRaisesRegex(ValueError, "Tamanho registrado:.*GPK atual:") as error:
            self.service.refresh(names=["Test"], **self.kw)
        self.assertIn("Test.gpk", str(error.exception))
        self.assertEqual(self.service.file_path("Test", "DATA/RAW.BIN").read_bytes(), FILES["DATA/RAW.BIN"])

    def test_reference_replacement_same_size_still_invalidates_offsets(self):
        self.service.detect(**self.kw)
        original_size = (self.packs / "Test.gpk").stat().st_size
        replacement = dict(FILES)
        replacement["DATA/RAW.BIN"] = FILES["DATA/RAW.BIN"][:4] + b"x" * (len(FILES["DATA/RAW.BIN"]) - 4)
        make_archive(self.packs / "Test.gpk", replacement)
        self.assertEqual((self.packs / "Test.gpk").stat().st_size, original_size)
        # Force a distinguishable modification time even on coarse filesystems.
        import os
        path = self.packs / "Test.gpk"
        stamp = path.stat()
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 2_000_000_000))
        with patch("sdhq_toolkit.core.desktop.read_stack_index", wraps=__import__(
            "sdhq_toolkit.formats.gpk.index", fromlist=["read_stack_index"]).read_stack_index) as read:
            self.service.catalog(**self.kw)
        read.assert_called_once()

    def test_refresh_all_six_states_and_restore(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI", "INI/TWO.INI"]}, **self.kw)
        one = self.service.file_path("Test", "INI/ONE.INI")
        two = self.service.file_path("Test", "INI/TWO.INI")
        self.assertEqual(self.service.refresh(**self.kw)[0]["state"], "original")
        one.write_bytes(b"[Settings]\r\nvalue=modified\r\n")
        two.unlink()
        new = one.parent / "NEW.INI"
        new.write_bytes(b"new")
        rows = self.service.refresh(**self.kw)
        self.assertEqual([r["state"] for r in rows], ["modificado", "ausente", "não extraído", "novo"])
        one.write_bytes(b"[BrokenStructure]\r\nother=value\r\n")
        self.assertEqual(self.service.refresh(**self.kw)[0]["state"], "inválido")
        self.service.extract({"Test": ["INI/ONE.INI"]}, restore=True, **self.kw)
        self.assertEqual(one.read_bytes(), FILES["INI/ONE.INI"])

    def test_specs_before_extraction_do_not_change_workspace(self):
        self.service.detect(**self.kw)
        details = self.service.inspect("Test", "INI/ONE.INI", cancel=self.kw["cancel"])
        self.assertEqual(details["original"]["encoding"], "UTF-8")
        self.assertEqual(details["original"]["keys"], ["value"])
        self.assertFalse(self.service.settings.workspace.exists())
        unknown = self.service.inspect("Test", "DATA/RAW.BIN", cancel=self.kw["cancel"])
        self.assertIn("signature", unknown["original"])
        self.assertTrue(unknown["warnings"])

    def test_repack_preflight_blocks_new_files_and_protects_packs(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)
        (self.service.settings.workspace / "Test/new.txt").write_text("new")
        original = (self.packs / "Test.gpk").read_bytes()
        with self.assertRaises(ValueError):
            self.service.repack({"Test": []}, **self.kw)
        self.assertEqual((self.packs / "Test.gpk").read_bytes(), original)
        self.assertFalse(self.service.settings.output.exists())

    def test_output_and_workspace_overlap_rejected(self):
        with self.assertRaises(ValueError):
            Settings(self.root, self.packs, self.root / "workspace", self.root / "reports", self.packs / "output").validate()
        with self.assertRaises(ValueError):
            Settings(self.root, self.packs, self.root / "workspace", self.root / "reports", self.root / "workspace/output").validate()

    def test_edit_after_validation_blocks_repack(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)
        preflight = self.service.preflight
        def change_after_validation(*args, **kwargs):
            rows = preflight(*args, **kwargs)
            self.service.file_path("Test", "INI/ONE.INI").write_bytes(b"invalid external edit")
            return rows
        with patch.object(self.service, "preflight", side_effect=change_after_validation):
            with self.assertRaisesRegex(ValueError, "changed since validation"):
                self.service.repack({"Test": []}, **self.kw)
        self.assertFalse((self.service.settings.output / "Test.gpk").exists())
        self.assertFalse((self.service.settings.output / "Test.gpk.tmp").exists())

    def test_apply_auto_extracts_only_package_targets_and_remove_restores(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI"]}, **self.kw)
        self.service.file_path("Test", "INI/ONE.INI").write_bytes(b"[Settings]\r\nvalue=edited\r\n")
        project = self.root / "project"
        mods.create_mod_project(project, mod_id="gui.partial", name="Test", author="Test", version="1")
        preview = self.service.package(project, **self.kw)
        result = self.service.package(project, preview=False, expected=preview["files"], **self.kw)
        target = DesktopService(Settings(self.root, self.packs, self.root / "target", self.root / "target-reports", self.root / "target-output"), KEY)
        target.detect(**self.kw)
        target.apply_package(Path(result["output"]), **self.kw)
        self.assertFalse(target.file_path("Test", "INI/TWO.INI").exists())
        target.remove_package("gui.partial", **self.kw)
        self.assertEqual(target.file_path("Test", "INI/ONE.INI").read_bytes(), FILES["INI/ONE.INI"])

    def test_job_background_result_report_and_exclusion(self):
        jobs = JobController()
        entered, release = threading.Event(), threading.Event()
        main_id = threading.get_ident()
        def operation(cancel, progress):
            entered.set()
            release.wait(3)
            progress(1, 1, "done")
            return {"thread": threading.get_ident()}
        jobs.start("test", operation, self.root / "reports")
        self.assertTrue(entered.wait(3))
        with self.assertRaises(RuntimeError):
            jobs.start("other", operation)
        release.set()
        jobs.thread.join(5)
        event = jobs.events.get_nowait()
        self.assertEqual(event[2], "PASS")
        self.assertNotEqual(event[3]["thread"], main_id)
        self.assertTrue(event[4].is_file())
        self.assertTrue((self.root / "reports/desktop.log").is_file())

    def test_job_cancel_and_error_are_reported(self):
        jobs = JobController()
        entered, release = threading.Event(), threading.Event()
        def operation(cancel, progress):
            entered.set()
            release.wait(3)
            cancel.check()
        jobs.start("cancel", operation)
        self.assertTrue(entered.wait(3))
        jobs.cancel()
        release.set()
        jobs.thread.join(5)
        self.assertEqual(jobs.events.get_nowait()[2], "CANCELLED")
        def broken(**_):
            raise ValueError("expected failure")
        jobs.start("error", broken)
        jobs.thread.join(5)
        event = jobs.events.get_nowait()
        self.assertEqual(event[2:4], ("FAIL", "expected failure"))

    def test_package_apply_cancellation_rolls_back_and_remove_resumes(self):
        self.service.detect(**self.kw)
        self.service.extract({"Test": ["INI/ONE.INI", "INI/TWO.INI"]}, **self.kw)
        for relative in ("INI/ONE.INI", "INI/TWO.INI"):
            self.service.file_path("Test", relative).write_bytes(b"[Settings]\r\nvalue=edited\r\n")
        project = self.root / "project"
        mods.create_mod_project(project, mod_id="gui.cancel", name="Test", author="Test", version="1")
        preview = self.service.package(project, **self.kw)
        report = self.service.package(project, preview=False, expected=preview["files"], **self.kw)
        self.service.extract({"Test": ["INI/ONE.INI", "INI/TWO.INI"]}, restore=True, **self.kw)
        def interrupt_second(index, total, path):
            if index == 2:
                raise OperationCancelled()
        with self.assertRaises(OperationCancelled):
            mods.apply_mod_package(Path(report["output"]), self.service.settings.workspace, progress=interrupt_second)
        for relative in ("INI/ONE.INI", "INI/TWO.INI"):
            self.assertEqual(self.service.file_path("Test", relative).read_bytes(), FILES[relative])
        self.service.apply_package(Path(report["output"]), **self.kw)
        with self.assertRaises(OperationCancelled):
            self.service.remove_package("gui.cancel", cancel=CancellationToken(), progress=interrupt_second)
        self.assertTrue(self.service.installed_mods()[0]["installed"])
        self.service.remove_package("gui.cancel", **self.kw)
        self.assertFalse(self.service.installed_mods()[0]["installed"])
        for relative in ("INI/ONE.INI", "INI/TWO.INI"):
            self.assertEqual(self.service.file_path("Test", relative).read_bytes(), FILES[relative])
