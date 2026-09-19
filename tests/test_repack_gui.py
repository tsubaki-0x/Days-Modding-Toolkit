"""Optional hidden-window checks for the new primary workflow."""
import os
import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from test_partial import KEY, make_archive
from sdhq_toolkit.gui.repack_app import RepackApplication
from sdhq_toolkit.gui.repack_controller import RepackSettings


@unittest.skipUnless(os.environ.get('SDHQ_GUI_TESTS') == '1', 'opt-in hidden Tk widget tests')
class RepackGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        for target, value in [
            ('sdhq_toolkit.gui.repack_app.RepackSettings', lambda _: RepackSettings(self.directory / 'settings.json')),
            ('sdhq_toolkit.gui.repack_app.messagebox.showerror', lambda *a, **k: self.errors.append(a)),
            ('sdhq_toolkit.core.folder_repack.find_ciphercode', lambda _: dict(found=True, key_hex=KEY.hex()))]:
            mock = patch(target, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.app = RepackApplication(self.root)
        reference = self.directory / 'base' / 'Test.gpk'
        reference.parent.mkdir()
        make_archive(reference)
        folder = self.directory / 'edits'
        (folder / 'INI').mkdir(parents=True)
        (folder / 'INI/ONE.INI').write_bytes(b'[Changed]\nvalue=edited\n')
        for key, value in dict(reference=reference, folder=folder, game=self.directory,
                               output=self.directory / 'output', reports=self.directory / 'reports').items():
            self.app.values[key].set(str(value))

    def tearDown(self):
        self.app.jobs.cancel()
        if self.app.jobs.thread:
            self.app.jobs.thread.join(5)
        for token in self.root.tk.call('after', 'info'):
            self.root.after_cancel(token)
        self.root.destroy()
        self.app = None
        self.root = None
        gc.collect()

    def click(self, label):
        button = next(c for c in self.app.controls if c.winfo_class() == 'TButton' and c.cget('text') == label)
        button.invoke()

    def settle(self):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.root.update()
            if not self.app.jobs.busy and self.app.jobs.events.empty() and self.app.cancel_button.instate(['disabled']):
                return
            time.sleep(.01)
        self.fail('Worker did not finish')

    def test_preview_and_repack_buttons_without_garbro(self):
        self.click('Conferir alterações')
        self.settle()
        self.assertIn('1 substituições', self.app.status.get())
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.click('Gerar GPK')
        self.settle()
        self.assertIn('GPK gerado com avisos', self.app.status.get())
        self.assertTrue((self.directory / 'output/Test.gpk').is_file())
        self.assertTrue(self.app.last_report.is_file())
        self.assertEqual(self.errors, [])

    def test_missing_garbro_and_missing_reference_give_feedback(self):
        self.click('Abrir GARbro')
        self.assertIn('Selecione o GARbro.exe', self.app.status.get())
        self.app.values['reference'].set('')
        self.click('Gerar GPK')
        self.assertIn('Preencha', self.app.status.get())
        self.assertEqual(len(self.errors), 2)
        self.assertFalse(self.app.jobs.busy)

    def test_theme_keeps_table_and_controls_visible_at_minimum_size(self):
        self.root.attributes('-alpha', 0)
        self.root.geometry('980x800')
        self.root.deiconify()
        self.root.update()
        self.assertGreaterEqual(self.app.table.winfo_height(), 90)
        for widget in [self.app.detail]:
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
        self.assertTrue(any(getattr(widget, 'image', None) for widget in self.app.header.winfo_children()))

    def test_reference_key_switches_visual_theme(self):
        from unittest.mock import patch as local_patch
        self.app._reference_theme_stamp = None
        with local_patch("sdhq_toolkit.gui.repack_app.read_stack_index",
                         return_value={"index_key_name": "SHINY_DAYS"}):
            self.app._detect_reference_theme(announce=True)
        self.root.update()
        self.assertEqual(self.app.theme_id, "shiny_days")
        self.assertIn("Shiny Days", self.root.title())
        self.assertIn("Tema aplicado automaticamente", self.app.status.get())

    def test_results_remain_visible_when_resizing(self):
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        for size in ('760x540', '1024x650', '1366x700', '1460x900'):
            self.root.geometry(size)
            self.root.update()
            self.assertGreaterEqual(self.app.table.winfo_height(), 90, size)
            self.assertLessEqual(self.app.detail.winfo_rooty() + self.app.detail.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height(), size)
        self.app.form.canvas.yview_moveto(1)
        self.root.update()
        self.assertGreater(self.app.form.canvas.yview()[0], 0)
