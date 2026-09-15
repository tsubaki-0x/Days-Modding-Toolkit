import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_partial import make_archive, KEY, FILES
from sdhq_toolkit.core.folder_repack import FolderRepackService
from sdhq_toolkit.core.operations import CancellationToken, OperationCancelled
from sdhq_toolkit.formats.gpk.reader import GPKReader
from sdhq_toolkit.gui.repack_controller import RepackSettings, garbro_status, launch_garbro


class FolderRepackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reference = self.root / 'base' / 'Test.gpk'
        self.reference.parent.mkdir()
        make_archive(self.reference)
        self.folder = self.root / 'edits'
        self.folder.mkdir()
        self.service = FolderRepackService(self.reference, self.folder, key=KEY)

    def put(self, name, data):
        path = self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def verify(self, report, expected):
        destination = self.root / 'verify'
        GPKReader(Path(report['output']), KEY).extract(destination)
        for name, data in expected.items():
            self.assertEqual((destination / name).read_bytes(), data)

    def test_external_folder_ignores_stale_metadata_preserves_missing(self):
        self.put('.sdhq/archive.json', b'invalid old metadata')
        self.put('INI/ONE.INI', b'[Other]\r\nchanged=yes\r\n')
        report = self.service.build(self.root / 'output')
        self.assertEqual(report['status'], 'WARN')
        self.assertEqual(report['modified_entries'], 1)
        self.verify(report, dict(FILES, **{'INI/ONE.INI': b'[Other]\r\nchanged=yes\r\n'}))
        self.assertEqual((self.folder / '.sdhq/archive.json').read_bytes(), b'invalid old metadata')

    def test_empty_folder_keeps_reference(self):
        report = self.service.build(self.root / 'output')
        self.assertEqual(report['modified_entries'], 0)
        self.assertFalse((self.folder / '.sdhq').exists())
        self.verify(report, FILES)

    def test_modified_reference_is_freshly_read(self):
        modified = dict(FILES, **{'INI/TWO.INI': b'[NewBase]\nvalue=longer modified reference\n'})
        make_archive(self.reference, modified)
        report = self.service.build(self.root / 'output')
        self.verify(report, modified)

    def test_extras_are_explicit_warnings_not_blockers(self):
        self.put('NEW.TXT', b'new asset')
        plan = self.service.preview()
        self.assertEqual(plan['extras'], ['NEW.TXT'])
        report = self.service.build(self.root / 'output')
        self.assertEqual(report['status'], 'WARN')
        self.assertEqual(report['entry_count'], len(FILES))
        self.assertTrue(any(row['path'] == 'NEW.TXT' for row in report['files']))

    def test_equal_files_and_short_raw_replacement(self):
        self.put('INI/ONE.INI', FILES['INI/ONE.INI'])
        self.put('DATA/RAW.BIN', b'x')
        plan = self.service.preview()
        self.assertEqual(plan['unchanged'], 1)
        self.assertEqual(plan['replacements'], 1)
        report = self.service.build(self.root / 'output')
        self.verify(report, dict(FILES, **{'DATA/RAW.BIN': b'x'}))

    def test_cancelled_build_leaves_no_output(self):
        token = CancellationToken()
        def progress(*_):
            token.cancel()
        with self.assertRaises(OperationCancelled):
            self.service.build(self.root / 'output', cancel=token, progress=progress)
        self.assertFalse((self.root / 'output/Test.gpk').exists())

    def test_repeated_build_preserves_previous_output(self):
        first = self.service.build(self.root / 'output')
        data = Path(first['output']).read_bytes()
        second = self.service.build(self.root / 'output')
        self.assertNotEqual(first['output'], second['output'])
        self.assertEqual(Path(first['output']).read_bytes(), data)

    def test_output_cannot_contaminate_source(self):
        with self.assertRaises(ValueError):
            self.service.build(self.folder / 'output')
        with self.assertRaises(ValueError):
            self.service.build(self.reference.parent)

    def test_root_entries_use_folder_contents_not_folder_name(self):
        files = {'ONE.INI': b'[Settings]\nvalue=one\n', 'TWO.INI': b'[Settings]\nvalue=two\n'}
        make_archive(self.reference, files)
        changed = b'[Settings]\nvalue=edited\n'
        self.put('ONE.INI', changed)
        plan = self.service.preview()
        self.assertEqual(plan['replacements'], 1)
        self.assertEqual(plan['retained'], 1)
        report = self.service.build(self.root / 'output')
        self.assertEqual(Path(report['output']).name, self.reference.name)
        self.verify(report, dict(files, **{'ONE.INI': changed}))

    def test_cancel_during_writer_removes_temporary_and_preserves_inputs(self):
        self.put('INI/ONE.INI', b'[Settings]\nvalue=changed\n')
        original = self.reference.read_bytes()
        token = CancellationToken()
        def progress(*event):
            if len(event) == 4:  # Writer callback; preview emits only 3 arguments.
                token.cancel()
        with self.assertRaises(OperationCancelled):
            self.service.build(self.root / 'output', cancel=token, progress=progress)
        self.assertFalse((self.root / 'output/Test.gpk').exists())
        self.assertFalse((self.root / 'output/Test.gpk.tmp').exists())
        self.assertEqual(self.reference.read_bytes(), original)
        self.assertEqual((self.folder / 'INI/ONE.INI').read_bytes(), b'[Settings]\nvalue=changed\n')

    def test_reference_change_during_preview_is_detected(self):
        def progress(number, *_):
            if number == 1:
                make_archive(self.reference, {'OTHER.INI': b'new reference'})
        with self.assertRaisesRegex(ValueError, 'referência mudou'):
            self.service.preview(progress=progress)


class RepackControllerTests(unittest.TestCase):
    def test_manual_configuration_persists_without_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = RepackSettings(root / 'settings.json')
            self.assertEqual(settings.load(), {})
            exe = root / 'GARbro.exe'
            exe.write_bytes(b'placeholder')
            settings.save({'garbro': str(exe)})
            self.assertEqual(settings.load()['garbro'], str(exe))
            self.assertEqual(garbro_status(str(exe)), 'GARbro configurado')
            with patch('sdhq_toolkit.gui.repack_controller.subprocess.Popen') as popen:
                launch_garbro(str(exe))
                popen.assert_called_once_with([str(exe)], cwd=str(root))
            exe.unlink()
            self.assertEqual(garbro_status(str(exe)), 'Executável não encontrado')
            with self.assertRaises(ValueError):
                launch_garbro(str(exe))
            self.assertEqual(garbro_status(''), 'Não configurado')
