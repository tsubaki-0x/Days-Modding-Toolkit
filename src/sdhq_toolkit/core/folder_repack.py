"""Repack external extraction folders; no persistent extraction metadata required."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from .asset_validation import _format_name, _inspect_asset, _compare_properties
from .operations import OperationCancelled
from .key_extractor import find_ciphercode
from ..formats.gpk.index import read_stack_index
from ..formats.gpk.reader import GPKReader
from ..formats.gpk.writer import GPKWriter
from ..utils.hashing import sha256_file
from ..utils.paths import safe_member_path


def stamp(path):
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)


class FolderRepackService:
    def __init__(self, reference, folder, game=None, *, key=None):
        self.reference = Path(reference).resolve()
        self.folder = Path(folder).resolve()
        self.game = Path(game).resolve() if game else None
        self.key = key

    def preview(self, *, cancel=None, progress=None):
        if not self.reference.is_file() or not self.folder.is_dir():
            raise ValueError("Selecione um GPK de referência e uma pasta de alterações existentes.")
        if self.key is None:
            if self.game is None:
                raise ValueError("Selecione a instalação do jogo para ler a chave do GPK.")
            result = find_ciphercode(self.game)
            if not result['found']:
                raise ValueError("CIPHERCODE não encontrado na instalação selecionada.")
            self.key = bytes.fromhex(result['key_hex'])
        reference_stamp = stamp(self.reference)
        index = read_stack_index(self.reference, self.key)
        entries, rows, warnings, hashes = [], [], [], {}
        declared = set()
        for number, entry in enumerate(index['entries'], 1):
            if cancel:
                cancel.check()
            path = safe_member_path(self.folder, entry['path'])
            if path in declared:
                raise ValueError(f"Caminho duplicado ou ambíguo no índice: {entry['path']}")
            declared.add(path)
            record = dict(entry, extracted=path.is_file())
            state = 'manter referência'
            notes = []
            if path.exists() and not path.is_file():
                notes.append('O caminho é uma pasta; será mantida a entrada da referência.')
            if path.is_file():
                before = stamp(path)
                current = sha256_file(path, cancel=cancel)
                hashes[entry['path']] = current
                # Only one original entry exists on disk at a time, outside the user's folder.
                with tempfile.TemporaryDirectory(prefix='sdhq-compare-') as temporary:
                    extracted = GPKReader(self.reference, self.key).extract(
                        Path(temporary), index_report=dict(index, entries=[entry]), cancel=cancel)
                    baseline = extracted['entries'][0]['extracted_sha256']
                    record['extracted_sha256'] = baseline
                    state = 'igual' if current == baseline else 'substituir'
                    if state == 'substituir':
                        original = safe_member_path(Path(temporary), entry['path'])
                        try:
                            fmt = _format_name(path)
                            old = _inspect_asset(original, fmt, full_validation=True)
                            new = _inspect_asset(path, fmt, full_validation=True)
                            errors, advice = _compare_properties(fmt, old, new)
                            notes.extend(errors + advice)
                            if new.get('warning'):
                                notes.append(new['warning'])
                        except OperationCancelled:
                            raise
                        except Exception as exc:
                            notes.append(f'Inspeção de formato: {exc}')
                if stamp(path) != before:
                    raise ValueError(f'Arquivo alterado durante a comparação: {path}. Tente novamente.')
            entries.append(record)
            rows.append(dict(path=entry['path'], state=state, warnings=notes))
            warnings.extend(f"{entry['path']}: {note}" for note in notes)
            if progress:
                progress(number, len(index['entries']), entry['path'])
        extras = []
        for path in self.folder.rglob('*'):
            if cancel:
                cancel.check()
            if path.is_file() and '.sdhq' not in path.relative_to(self.folder).parts and path.resolve() not in declared:
                name = path.relative_to(self.folder).as_posix()
                extras.append(name)
                note = 'Não incluído: caminho fora do índice; inclusão de entradas novas ainda não implementada.'
                rows.append(dict(path=name, state='novo — não incluído', warnings=[note]))
                warnings.append(f'{name}: {note}')
        if stamp(self.reference) != reference_stamp:
            raise ValueError('A referência mudou durante a leitura. Compare novamente.')
        return dict(operation='folder_preview', status='WARN' if warnings else 'PASS',
                    reference=str(self.reference), folder=str(self.folder), reference_stamp=reference_stamp,
                    files=rows, warnings=warnings, extras=extras, expected_hashes=hashes,
                    metadata=dict(archive_size=index['archive_size'], entries=entries),
                    replacements=sum(row['state'] == 'substituir' for row in rows),
                    unchanged=sum(row['state'] == 'igual' for row in rows),
                    retained=sum(row['state'] == 'manter referência' for row in rows))

    def build(self, output_folder, *, cancel=None, progress=None):
        output_folder = Path(output_folder).resolve()
        # Keep generated archives outside both the reference directory and edited files.
        if (output_folder == self.reference.parent or
                output_folder == self.folder or self.folder in output_folder.parents):
            raise ValueError('Escolha uma saída separada da pasta de alterações e da pasta do GPK de referência.')
        plan = self.preview(cancel=cancel, progress=progress)
        output = output_folder / self.reference.name
        if output.exists():
            output = output_folder / ('repack-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')) / self.reference.name
        if stamp(self.reference) != plan['reference_stamp']:
            raise ValueError('A referência mudou. Tente novamente.')
        report = GPKWriter(self.reference, self.key).repack(
            self.folder, output, overlay_metadata=plan['metadata'],
            expected_hashes=plan['expected_hashes'], cancel=cancel, progress=progress)
        return dict(report, operation='folder_repack', status=plan['status'],
                    warnings=plan['warnings'], files=plan['files'],
                    message='GPK gerado com avisos' if plan['warnings'] else 'GPK gerado',
                    game_compatibility='Não garantida; teste no jogo.')
