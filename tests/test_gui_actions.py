"""Opt-in widget integration tests, with a hidden window and synthetic archives.

Set SDHQ_GUI_TESTS=1 to run. Ordinary unittest discovery remains headless.
No game files, external applications or existing workspace are modified.
"""
import os
import gc
import json
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from sdhq_toolkit.core.desktop import DesktopService, Settings
from sdhq_toolkit.core.operations import CancellationToken
from sdhq_toolkit.gui.app import Application
from sdhq_toolkit.formats.gpk.reader import GPKReader
from test_partial import FILES, KEY, make_archive


@unittest.skipUnless(os.environ.get("SDHQ_GUI_TESTS") == "1", "opt-in hidden Tk widget tests")
class GuiActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.packs = self.directory / "Packs"
        self.packs.mkdir()
        make_archive(self.packs / "Test.gpk")
        self.settings = Settings(self.directory, self.packs, self.directory / "workspace",
                                 self.directory / "reports", self.directory / "output")
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Application(self.root)
        self.app.config_path = self.directory / "settings.json"
        for name, variable in self.app.paths.items():
            variable.set(str(getattr(self.settings, name)))
        self.messages = []
        self.errors = []
        for name, replacement in (
            ("showinfo", lambda *a, **k: self.messages.append(a)),
            ("showerror", lambda *a, **k: self.errors.append(a)),
            ("askyesno", lambda *a, **k: True),
        ):
            active = patch("sdhq_toolkit.gui.app.messagebox." + name, replacement)
            active.start()
            self.addCleanup(active.stop)
        self.service = DesktopService(self.settings, KEY)
        rows = self.service.detect(cancel=CancellationToken(), progress=lambda *_: None)
        self.app.service = self.service
        self.app.accept_rows(rows)
        self.root.update()

    def tearDown(self):
        self.app.jobs.cancel()
        if self.app.jobs.thread:
            self.app.jobs.thread.join(5)
        # Cancel timer callbacks before destroying Tcl widgets.
        for token in self.root.tk.call("after", "info"):
            self.root.after_cancel(token)
        self.root.destroy()
        self.app = None
        self.root = None
        gc.collect()  # Dispose Tk cycles on their owning thread, before another worker starts.

    def button(self, text):
        def find(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and child.cget("text") == text:
                    return child
                found = find(child)
                if found is not None:
                    return found
            return None
        result = find(self.app.explorer)
        self.assertIsNotNone(result, text)
        return result

    def settle(self, allow_errors=False):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.root.update()
            if not self.app.jobs.busy and not self.app.callbacks and self.app.jobs.events.empty():
                break
            time.sleep(0.01)
        else:
            self.fail("GUI job did not finish")
        self.root.update()
        if not allow_errors:
            self.assertEqual(self.errors, [])

    def select_archive(self):
        node = next(node for node, value in self.app.folders.items() if value == ("Test", ""))
        self.app.tree.selection_set(node)
        self.root.update()

    def select_file(self, path="INI/ONE.INI"):
        index = next(i for i, row in enumerate(self.app.filtered) if row["path"] == path)
        self.app.table.selection_set(str(index))
        self.root.update()

    def test_detect_button_starts_with_empty_index(self):
        self.app.service = None
        with patch("sdhq_toolkit.gui.app.DesktopService", side_effect=lambda settings: DesktopService(settings, KEY)):
            self.app.detect_button.invoke()
            self.settle()
        self.assertEqual(len(self.app.rows), 3)
        self.assertTrue(self.app.config_path.is_file())
        self.assertEqual(self.app.tabs.select(), str(self.app.explorer))

    def test_validation_blocked_then_experimental_build_keeps_edited_content(self):
        self.button("Extrair tudo").invoke()
        self.settle()
        edited = b"[ChangedStructure]\r\nnew_key=longer edited value\r\n"
        self.service.file_path("Test", "INI/ONE.INI").write_bytes(edited)
        self.select_archive()
        self.button("Atualizar / validar").invoke()
        self.settle()
        self.assertIn("BLOQUEADO", self.app.status.get())
        report = json.loads(self.app.last_report.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["result"]["can_repack"])
        self.app.compatibility_mode.set("Experimental")
        self.button("Atualizar / validar").invoke()
        self.settle()
        self.assertIn("COM AVISOS", self.app.status.get())
        self.button("Repack GPKs selecionados").invoke()
        self.settle()
        self.assertIn("concluído com avisos", self.app.status.get())
        output = self.settings.output / "Test.gpk"
        verify = self.directory / "verify"
        GPKReader(output, KEY).extract(verify)
        self.assertEqual((verify / "INI/ONE.INI").read_bytes(), edited)
        first_bytes = output.read_bytes()
        self.button("Repack GPKs selecionados").invoke()
        self.settle()
        self.assertIn("repack-", self.app.status.get())
        self.assertEqual(output.read_bytes(), first_bytes)

    def test_unknown_format_authorization_is_on_explorer_and_shared(self):
        self.button("Extrair tudo").invoke()
        self.settle()
        self.service.file_path("Test", "DATA/RAW.BIN").write_bytes(b"edited unknown bytes")
        self.select_archive()
        self.button("Atualizar / validar").invoke()
        self.settle()
        self.assertIn("BLOQUEADO", self.app.status.get())
        self.app.action_buttons["Formatos desconhecidos"].invoke()
        self.assertTrue(self.app.allow_unknown.get())
        self.button("Atualizar / validar").invoke()
        self.settle()
        self.assertIn("COM AVISOS", self.app.status.get())

    def test_extract_gpk_button_finishes_without_automatic_validation(self):
        self.select_archive()
        with patch.object(self.service, "refresh", side_effect=AssertionError("unexpected validation")):
            self.button("Extrair seleção").invoke()
            self.settle()
            self.assertEqual(len(self.app.tree.selection()), 1)
            for path, content in FILES.items():
                self.assertEqual(self.service.file_path("Test", path).read_bytes(), content)
            summary = self.app.detail_text.get("1.0", "end")
            self.assertIn("3 extraídos agora", summary)
            self.assertIn("Concluído", self.app.status.get())
            self.button("Extrair seleção").invoke()
            self.settle()
            self.assertIn("3 já extraídos", self.app.detail_text.get("1.0", "end"))

    def test_extract_all_validate_specs_restore_and_repack_buttons(self):
        self.button("Extrair tudo").invoke()
        self.settle()
        file = self.service.file_path("Test", "INI/ONE.INI")
        file.write_bytes(b"[Settings]\r\nvalue=changed\r\n")
        self.select_file()
        self.button("Atualizar / validar").invoke()
        self.settle()
        self.assertEqual(self.app.selected_files(), [("Test", "INI/ONE.INI")])
        self.assertEqual(self.app.filtered[0]["state"], "modificado")
        self.button("Especificações").invoke()
        self.settle()
        self.assertIn('"original"', self.app.detail_text.get("1.0", "end"))
        self.button("Restaurar arquivo").invoke()
        self.settle()
        self.assertEqual(file.read_bytes(), FILES["INI/ONE.INI"])
        self.assertIn("1 restaurados", self.app.detail_text.get("1.0", "end"))
        self.button("Repack GPKs selecionados").invoke()
        self.settle()
        self.assertTrue((self.settings.output / "Test.gpk").is_file())
        self.assertIn("Repack concluído", self.app.status.get())

    def test_repack_all_ignores_search_filter(self):
        self.app.query.set("no matching file")
        self.button("Filtrar").invoke()
        self.assertEqual(self.app.filtered, [])
        self.button("Repack todos os GPKs").invoke()
        self.settle()
        self.assertTrue((self.settings.output / "Test.gpk").is_file())

    def test_missing_selection_and_open_file_folder_feedback(self):
        self.button("Extrair seleção").invoke()
        self.button("Repack GPKs selecionados").invoke()
        self.assertEqual(len(self.messages), 2)
        self.assertFalse(self.app.jobs.busy)
        self.select_file()
        self.button("Abrir arquivo").invoke()
        self.assertIn("ainda não existe", self.messages[-1][1])
        self.button("Extrair seleção").invoke()
        self.settle()
        self.select_file()
        with patch("sdhq_toolkit.gui.app.os.startfile", create=True) as startfile:
            self.button("Abrir arquivo").invoke()
            self.button("Abrir pasta").invoke()
            file = self.service.file_path("Test", "INI/ONE.INI")
            self.assertEqual([call.args[0] for call in startfile.call_args_list], [str(file), str(file.parent)])

    def test_filters_pagination_and_mark_buttons(self):
        self.app.PAGE_SIZE = 1
        self.app.filter()
        self.app.table.selection_set("0")
        self.button("Marcar seleção").invoke()
        self.button("▶").invoke()
        self.assertEqual(self.app.page, 1)
        self.app.table.selection_set("1")
        self.button("Marcar seleção").invoke()
        self.assertEqual(len(self.app.marked), 2)
        self.button("◀").invoke()
        self.assertEqual(self.app.page, 0)
        self.button("Limpar marcas").invoke()
        self.assertFalse(self.app.marked)
        self.app.query.set("one")
        self.app.ext.set(".ini")
        self.button("Filtrar").invoke()
        self.assertEqual(len(self.app.filtered), 1)
        self.button("Marcar filtrados").invoke()
        self.assertEqual(self.app.marked, {("Test", "INI/ONE.INI")})
        self.button("Limpar").invoke()
        self.assertEqual(len(self.app.filtered), 3)

    def test_busy_buttons_cancel_and_reenable(self):
        entered, release = threading.Event(), threading.Event()
        def operation(cancel, progress):
            entered.set()
            release.wait(5)
            cancel.check()
        self.app.run("Blocking synthetic operation", operation)
        self.assertTrue(entered.wait(2))
        self.assertTrue(self.button("Extrair seleção").instate(["disabled"]))
        self.app.cancel_button.invoke()
        release.set()
        self.settle()
        self.assertIn("CANCELLED", self.app.status.get())
        self.assertFalse(self.button("Extrair seleção").instate(["disabled"]))
        self.assertTrue(self.app.cancel_button.instate(["disabled"]))

    def test_callback_failure_is_visible_and_polling_recovers(self):
        def broken(_):
            raise ValueError("synthetic callback failure")
        self.app.run("Callback test", lambda **_: [], broken)
        self.settle(allow_errors=True)
        self.assertIn("synthetic callback failure", self.errors[0][1])
        self.errors.clear()
        self.button("Extrair tudo").invoke()
        self.settle()
        self.assertTrue(self.service.file_path("Test", "INI/ONE.INI").is_file())

    def test_expanding_folder_shows_files_and_supports_file_actions(self):
        node = next(node for node, value in self.app.folders.items() if value == ("Test", "INI"))
        self.assertFalse(self.app.tree_files)
        self.app.tree.focus(node)
        self.app.tree.event_generate("<<TreeviewOpen>>")
        self.app.tree.item(node, open=True)
        self.root.update()
        names = [self.app.tree.item(child, "text") for child in self.app.tree.get_children(node)]
        self.assertEqual(names, ["ONE.INI", "TWO.INI"])
        leaf = next(leaf for leaf, value in self.app.tree_files.items() if value == ("Test", "INI/ONE.INI"))
        self.app.tree.selection_set(leaf)
        self.root.update()
        self.assertEqual(self.app.selected_files(), [("Test", "INI/ONE.INI")])
        self.assertEqual(len(self.app.filtered), 2)
        self.button("Extrair seleção").invoke()
        self.settle()
        self.assertTrue(self.service.file_path("Test", "INI/ONE.INI").is_file())
        self.assertFalse(self.service.file_path("Test", "INI/TWO.INI").exists())
        self.button("Especificações").invoke()
        self.settle()
        self.assertIn('"original"', self.app.detail_text.get("1.0", "end"))

    def test_tree_multiselection_spanning_pages_keeps_every_file(self):
        node = next(node for node, value in self.app.folders.items() if value == ("Test", "INI"))
        self.app.populate_folder(node)
        self.app.PAGE_SIZE = 1
        leaves = list(self.app.tree_files)
        self.app.tree.selection_set(leaves)
        self.root.update()
        self.assertEqual(self.app.selection(), {"Test": ["INI/ONE.INI", "INI/TWO.INI"]})
        self.button("Extrair seleção").invoke()
        self.settle()
        self.assertTrue(self.service.file_path("Test", "INI/TWO.INI").is_file())

    def test_empty_filter_explains_why_files_are_hidden(self):
        self.app.query.set("not present")
        self.button("Filtrar").invoke()
        self.assertIn("Nenhum arquivo", self.app.empty_list_text.get())
        self.button("Limpar").invoke()
        self.assertEqual(self.app.empty_list_text.get(), "")
        self.assertEqual(len(self.app.table.get_children()), 3)

    def test_file_panel_can_be_recovered_at_minimum_window_size(self):
        # Real geometry calculation while the window remains fully transparent.
        self.root.attributes("-alpha", 0.0)
        self.root.geometry("1060x720")
        self.root.deiconify()
        self.root.update()
        self.app.browser_panes.sashpos(0, self.app.browser_panes.winfo_width() - 5)
        self.root.update()
        self.button("Mostrar painel de arquivos →").invoke()
        self.root.update()
        self.assertGreater(self.app.table.winfo_width(), 250)
        self.assertGreater(self.app.table.winfo_height(), 70)
        self.assertEqual(len(self.app.table.get_children()), 3)
