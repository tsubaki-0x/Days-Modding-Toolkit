"""Desktop frontend for GPK and Summer Days CRio reference repacking."""
import os
import queue
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .. import __version__
from ..core.folder_repack import FolderRepackService
from ..core.summer_days_crio import SummerDaysCRioService
from ..formats.gpk.index import read_stack_index
from .controller import JobController
from .repack_controller import RepackSettings, garbro_status, launch_garbro
from .theme import (
    DEFAULT_THEME_ID, SUMMER_THEME_ID, apply_theme, add_header, load_theme_profile, palette,
    theme_for_index_key, update_header,
)
from .background import ArtworkPanel
from .scroll_form import ScrollForm


class RepackApplication:
    def __init__(self, root):
        self.root = root
        root.title(f'Days ModToolkit {__version__} — School Days HQ / Shiny Days / Summer Days')
        root.geometry(f'{min(1460, root.winfo_screenwidth() - 60)}x{min(900, root.winfo_screenheight() - 100)}')
        root.minsize(760, 540)
        self.theme_id = DEFAULT_THEME_ID
        self.theme_profile = load_theme_profile(self.theme_id)
        self.style = apply_theme(root, self.theme_profile)
        self._theme_after = None
        self._reference_theme_stamp = None
        self.settings = RepackSettings(Path.cwd() / '.sdhq-repack.json')
        self.jobs = JobController()
        self.closing = False
        self.last_report = None
        self.controls = []
        self.artwork = ArtworkPanel(root, self.theme_id)
        self.artwork.pack(side='right', fill='y', padx=(0, 12), pady=12)

        def arrange_artwork(event):
            if event.widget is root:
                visible = event.width >= 1280
                if visible and not self.artwork.winfo_manager():
                    self.artwork.pack(side='right', fill='y', padx=(0, 12), pady=12, before=shell)
                elif not visible and self.artwork.winfo_manager():
                    self.artwork.pack_forget()

        root.bind('<Configure>', arrange_artwork, add='+')
        shell = ttk.Frame(root, padding=8)
        shell.pack(fill='both', expand=True, padx=12, pady=12)
        self.panes = ttk.Panedwindow(shell, orient='vertical')
        self.panes.pack(fill='both', expand=True)
        self.form = ScrollForm(self.panes)
        self.form.set_background(palette(self.theme_profile)['navy'])
        self.panes.add(self.form, weight=1)
        frame = self.form.body
        results = ttk.Frame(self.panes, padding=8)
        self.panes.add(results, weight=1)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.header = add_header(frame, __version__, self.theme_profile)
        self.mode_tabs = ttk.Notebook(frame)
        self.mode_tabs.pack(fill='x', expand=False, pady=(4, 8))
        gpk_frame = ttk.Frame(self.mode_tabs, padding=10)
        summer_frame = ttk.Frame(self.mode_tabs, padding=10)
        self.mode_tabs.add(gpk_frame, text='School Days HQ / Shiny Days · GPK')
        self.mode_tabs.add(summer_frame, text='Summer Days · CRio')

        ttk.Label(gpk_frame, text='School Days HQ / Shiny Days — extraia no GARbro, edite e monte aqui.', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(gpk_frame, text='Use uma pasta exclusiva por GPK, preservando os caminhos internos e os formatos.', wraplength=880).pack(anchor='w', pady=(4, 12))
        fields = ttk.LabelFrame(gpk_frame, text='  01  /  Localizações GPK  ', padding=10)
        fields.pack(fill='x')
        fields.columnconfigure(1, weight=1)
        self.values = {}
        labels = [('garbro', 'GARbro.exe (opcional)', True), ('game', 'Instalação do jogo (opcional)', False),
                  ('reference', 'GPK de referência', True), ('folder', 'Pasta com as alterações', False),
                  ('output', 'Pasta de saída', False), ('reports', 'Pasta de relatórios', False)]
        for row, (key, label, file) in enumerate(labels):
            self.values[key] = tk.StringVar()
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=3)
            entry = ttk.Entry(fields, textvariable=self.values[key])
            entry.grid(row=row, column=1, sticky='ew', pady=3)
            button = ttk.Button(fields, text='Selecionar…', command=lambda k=key, f=file: self.choose(k, f))
            button.grid(row=row, column=2, padx=(8, 0))
            self.controls.extend([entry, button])
        self.garbro_label = tk.StringVar(value='Não configurado')
        ttk.Label(gpk_frame, textvariable=self.garbro_label).pack(anchor='w', pady=5)
        self.values['garbro'].trace_add('write', lambda *_: self.garbro_label.set(garbro_status(self.values['garbro'].get())))
        self.values['reference'].trace_add('write', self._schedule_reference_theme_detection)
        toolbar = ttk.Frame(gpk_frame)
        toolbar.pack(fill='x', pady=8)
        for index, (label, callback) in enumerate([('Abrir GARbro', self.open_garbro), ('Conferir alterações', lambda: self.start(False)),
                                ('Gerar GPK', lambda: self.start(True)), ('Abrir saída', lambda: self.open_path('output')),
                                ('Relatórios', lambda: self.open_path('reports')), ('Interface anterior / .sdmod', self.legacy)]):
            button = ttk.Button(toolbar, text=label, command=lambda cb=callback: self.guard(cb),
                                style='Primary.TButton' if label == 'Gerar GPK' else 'TButton')
            button.grid(row=index // 3, column=index % 3, sticky='ew', padx=(0, 6), pady=3)
            toolbar.columnconfigure(index % 3, weight=1)
            self.controls.append(button)
        ttk.Label(gpk_frame, text='Antes de trocar o GPK em Packs, feche o jogo e o GARbro e guarde uma cópia do GPK anterior.',
                  wraplength=1000).pack(anchor='w', pady=(4, 0))

        ttk.Label(summer_frame, text='Summer Days — CRio de referência → árvore editável → repack.', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(
            summer_frame,
            text='Não usa GARbro. O CRio original é a autoridade para árvore, nomes, classes, ordem, offsets e tamanhos. '
                 'A extração cria <workspace>/<nome do CRio>/ com a árvore completa editável.',
            wraplength=920,
        ).pack(anchor='w', pady=(4, 12))
        summer_fields = ttk.LabelFrame(summer_frame, text='  01  /  Localizações CRio  ', padding=10)
        summer_fields.pack(fill='x')
        summer_fields.columnconfigure(1, weight=1)
        self.summer_values = {}
        summer_labels = [
            ('game', 'Instalação do Summer Days (opcional)', False),
            ('reference', 'CRio de referência', True),
            ('workspace', 'Workspace de edição', False),
            ('output', 'Pasta de saída', False),
            ('reports', 'Pasta de relatórios', False),
        ]
        for row, (key, label, file) in enumerate(summer_labels):
            self.summer_values[key] = tk.StringVar()
            ttk.Label(summer_fields, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=3)
            entry = ttk.Entry(summer_fields, textvariable=self.summer_values[key])
            entry.grid(row=row, column=1, sticky='ew', pady=3)
            button = ttk.Button(summer_fields, text='Selecionar…', command=lambda k=key, f=file: self.choose_summer(k, f))
            button.grid(row=row, column=2, padx=(8, 0))
            self.controls.extend([entry, button])

        summer_toolbar = ttk.Frame(summer_frame)
        summer_toolbar.pack(fill='x', pady=8)
        summer_actions = [
            ('Ler CRio', self.summer_inspect),
            ('Extrair CRio', self.summer_extract),
            ('Conferir alterações', self.summer_validate),
            ('Gerar CRio', self.summer_repack),
            ('Abrir workspace', lambda: self.open_summer_path('workspace')),
            ('Abrir saída', lambda: self.open_summer_path('output')),
        ]
        for index, (label, callback) in enumerate(summer_actions):
            button = ttk.Button(
                summer_toolbar,
                text=label,
                command=lambda cb=callback: self.guard(cb),
                style='Primary.TButton' if label == 'Gerar CRio' else 'TButton',
            )
            button.grid(row=index // 3, column=index % 3, sticky='ew', padx=(0, 6), pady=3)
            summer_toolbar.columnconfigure(index % 3, weight=1)
            self.controls.append(button)
        ttk.Label(
            summer_frame,
            text='Metadados técnicos ficam em <workspace>/.crio e não precisam ser editados. '
                 'Arquivos novos não viram objetos CRio; arquivos removidos bloqueiam o repack.',
            wraplength=1000,
        ).pack(anchor='w', pady=(4, 0))
        self.mode_tabs.bind('<<NotebookTabChanged>>', self._mode_changed)
        self.cancel_button = ttk.Button(frame, text='Cancelar operação', command=self.cancel, state='disabled')
        self.cancel_button.pack(anchor='e')
        self.status = tk.StringVar(value='Pronto. Selecione a referência e a pasta de alterações.')
        ttk.Label(frame, textvariable=self.status, wraplength=880).pack(anchor='w', pady=5)
        self.bar = ttk.Progressbar(frame)
        self.bar.pack(fill='x', pady=5)
        table_frame = ttk.LabelFrame(results, text='  02  /  Arquivos e alterações  ', padding=8)
        table_frame.grid(row=0, column=0, sticky='nsew')
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=('path', 'state', 'notes'), show='headings', height=5)
        for key, label, width in [('path', 'Caminho interno', 400), ('state', 'Ação', 160), ('notes', 'Avisos', 350)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.grid(row=0, column=0, sticky='nsew')
        colors = palette(self.theme_profile)
        self.detail = tk.Text(results, height=2, wrap='word', state='disabled',
                              background=colors['navy'], foreground=colors['white'],
                              selectbackground=colors['light'], selectforeground=colors['ink'], relief='flat',
                              highlightthickness=1, highlightbackground=colors['light'], padx=8, pady=6)
        self.detail.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.table.bind('<<TreeviewSelect>>', self.show_detail)
        ttk.Label(frame, text='Avisos de compatibilidade não substituem o teste final no jogo. Preserve sempre o arquivo original de referência.', wraplength=1000).pack(anchor='w', pady=5)
        self.guard(self.load)
        self.form.enable_navigation()
        root.report_callback_exception = lambda kind, error, trace: self.error(error)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def apply_game_theme(self, theme_id, *, key_name=None, announce=False):
        profile = load_theme_profile(theme_id, allow_root_override=(theme_id == DEFAULT_THEME_ID))
        self.theme_id = profile['id']
        self.theme_profile = profile
        self.style = apply_theme(self.root, profile)
        colors = palette(profile)
        self.artwork.set_theme(self.theme_id)
        self.form.set_background(colors['navy'])
        update_header(self.header, __version__, profile)
        self.detail.configure(
            background=colors['navy'], foreground=colors['white'],
            selectbackground=colors['light'], selectforeground=colors['ink'],
            highlightbackground=colors['light'],
        )
        game_name = profile.get('nome', 'Days')
        self.root.title(f'Days ModToolkit {__version__} — {game_name}')
        if announce and hasattr(self, 'status'):
            suffix = f' (chave {key_name})' if key_name else ''
            self.status.set(f'GPK reconhecido: {game_name}{suffix}. Tema aplicado automaticamente.')

    def _schedule_reference_theme_detection(self, *_):
        if self._theme_after:
            try:
                self.root.after_cancel(self._theme_after)
            except tk.TclError:
                pass
        self._theme_after = self.root.after(250, self._detect_reference_theme)

    def _detect_reference_theme(self, announce=False):
        self._theme_after = None
        raw = self.values.get('reference').get().strip() if self.values.get('reference') else ''
        if not raw:
            return
        path = Path(raw)
        if not path.is_file() or path.suffix.lower() != '.gpk':
            return
        try:
            stat = path.stat()
            stamp = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
            if self._reference_theme_stamp and self._reference_theme_stamp[:3] == stamp:
                if announce:
                    key_name = self._reference_theme_stamp[3]
                    theme_id = theme_for_index_key(key_name)
                    if theme_id:
                        self.apply_game_theme(theme_id, key_name=key_name, announce=True)
                return
            report = read_stack_index(path)
            key_name = report.get('index_key_name')
            self._reference_theme_stamp = (*stamp, key_name)
        except Exception:
            return
        theme_id = theme_for_index_key(key_name)
        if theme_id:
            self.apply_game_theme(theme_id, key_name=key_name, announce=announce)

    def guard(self, action):
        try:
            action()
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set(f'Falha: {exc}')
        messagebox.showerror('ModToolkit', str(exc), parent=self.root)

    def load(self):
        saved = self.settings.load()
        for key, value in self.values.items():
            value.set(saved.get(key, str(Path.cwd() / key) if key in ('output', 'reports') else ''))
        summer_defaults = {
            'game': '',
            'reference': '',
            'workspace': str(Path.cwd() / 'summer_workspace'),
            'output': str(Path.cwd() / 'summer_output'),
            'reports': str(Path.cwd() / 'reports'),
        }
        for key, value in self.summer_values.items():
            value.set(saved.get('summer_' + key, summer_defaults[key]))
        self.root.after(80, self._detect_reference_theme)

    def save(self):
        values = {key: value.get().strip() for key, value in self.values.items()}
        values.update({'summer_' + key: value.get().strip() for key, value in self.summer_values.items()})
        self.settings.save(values)

    def choose(self, key, file):
        def action():
            value = (filedialog.askopenfilename(parent=self.root, filetypes=[('Executável', '*.exe')] if key == 'garbro' else [('GPK', '*.gpk')])
                     if file else filedialog.askdirectory(parent=self.root))
            if value:
                self.values[key].set(value)
                self.save()
                self.status.set('Localização salva: ' + value)
                if key == 'reference':
                    self._detect_reference_theme(announce=True)
            else:
                self.status.set('Seleção cancelada; localização anterior mantida.')
        self.guard(action)

    def _mode_changed(self, *_):
        if not hasattr(self, 'mode_tabs'):
            return
        tab = self.mode_tabs.tab(self.mode_tabs.select(), 'text')
        if 'Summer Days' in tab:
            self.apply_game_theme(SUMMER_THEME_ID)
            return

        raw = self.values.get('reference').get().strip() if self.values.get('reference') else ''
        path = Path(raw) if raw else None
        if path and path.is_file() and path.suffix.lower() == '.gpk':
            # Force a visual refresh when returning from the Summer Days tab.
            # The technical GPK autodetection remains the authority for School/Shiny.
            self._reference_theme_stamp = None
            self._detect_reference_theme()
        else:
            self.apply_game_theme(DEFAULT_THEME_ID)

    def choose_summer(self, key, file):
        def action():
            if file:
                initial = None
                raw_game = self.summer_values['game'].get().strip()
                if raw_game:
                    game = Path(raw_game)
                    candidates = []
                    if game.name.casefold() == 'exe':
                        candidates.extend((game / 'rUGP.rio.Op', game))
                    else:
                        candidates.extend((game / 'EXE' / 'rUGP.rio.Op', game / 'rUGP.rio.Op', game))
                    for candidate in candidates:
                        if candidate.is_dir():
                            initial = str(candidate)
                            break
                value = filedialog.askopenfilename(
                    parent=self.root,
                    title='Selecionar CRio de referência',
                    initialdir=initial,
                    filetypes=[('Contêiner CRio', '*'), ('Todos os arquivos', '*.*')],
                )
            else:
                value = filedialog.askdirectory(parent=self.root)
            if value:
                self.summer_values[key].set(value)
                self.save()
                self.status.set('Localização Summer Days salva: ' + value)
            else:
                self.status.set('Seleção cancelada; localização anterior mantida.')
        self.guard(action)

    def _summer_service(self):
        values = {key: var.get().strip() for key, var in self.summer_values.items()}
        for key in ('reference', 'workspace', 'output', 'reports'):
            if not values[key]:
                raise ValueError('Preencha a localização Summer Days: ' + key)
        workspace = Path(values['workspace']).resolve()
        output = Path(values['output']).resolve()
        reports = Path(values['reports']).resolve()
        if reports == workspace or workspace in reports.parents:
            raise ValueError('Escolha relatórios fora do workspace CRio.')
        if output == workspace or output in workspace.parents or workspace in output.parents:
            raise ValueError('Workspace e saída CRio devem ficar separados.')
        return values, SummerDaysCRioService(
            values['reference'], workspace, output, values['game'] or None
        )

    def _launch_job(self, name, operation, reports, initial_status):
        if self.jobs.busy:
            raise ValueError('Aguarde ou cancele a operação atual.')
        self.jobs.start(name, operation, Path(reports).resolve())
        for control in self.controls:
            control.state(['disabled'])
        self.cancel_button.state(['!disabled'])
        self.status.set(initial_status)
        self.bar.configure(mode='indeterminate')
        self.bar.start()

    def summer_inspect(self):
        values, service = self._summer_service()
        self.save()
        self._launch_job(
            'Ler CRio',
            service.inspect_reference,
            values['reports'],
            'Lendo a estrutura CRio de referência…',
        )

    def summer_extract(self):
        values, service = self._summer_service()
        replace = False
        if service.edit_root.exists() or service.project_root.exists():
            replace = messagebox.askyesno(
                'Reextrair CRio',
                f'Já existe um workspace para {service.name}.\n\n'
                'Substituir a extração e DESCARTAR as edições atuais desse CRio?',
                parent=self.root,
            )
            if not replace:
                self.status.set('Extração cancelada; workspace existente preservado.')
                return
        self.save()
        self._launch_job(
            'Extrair CRio',
            lambda **kw: service.extract(replace=replace, **kw),
            values['reports'],
            'Extraindo o CRio para a árvore editável…',
        )

    def summer_validate(self):
        values, service = self._summer_service()
        self.save()
        self._launch_job(
            'Conferir CRio',
            service.validate,
            values['reports'],
            'Comparando a árvore editável com o CRio original…',
        )

    def summer_repack(self):
        values, service = self._summer_service()
        self.save()
        self._launch_job(
            'Gerar CRio',
            service.repack,
            values['reports'],
            'Validando e reconstruindo o CRio…',
        )

    def open_summer_path(self, key):
        raw = self.summer_values[key].get().strip()
        if not raw:
            raise ValueError('Localização Summer Days não configurada: ' + key)
        path = Path(raw)
        if key == 'workspace':
            reference = self.summer_values['reference'].get().strip()
            if reference:
                candidate = path / Path(reference).name
                if candidate.is_dir():
                    path = candidate
        if not path.is_dir():
            raise ValueError('A pasta ainda não existe: ' + str(path))
        os.startfile(str(path.resolve()))
        self.status.set('Pasta aberta: ' + str(path))

    def open_garbro(self):
        self.save()
        process = launch_garbro(self.values['garbro'].get().strip())
        self.status.set(f'GARbro iniciado (processo {process.pid}). Extraia e edite os arquivos antes de montar.')

    def open_path(self, key):
        value = self.values[key].get().strip()
        if not value or not Path(value).is_dir():
            raise ValueError('A pasta ainda não existe: ' + value)
        os.startfile(value)
        self.status.set('Pasta aberta: ' + value)

    def legacy(self):
        subprocess.Popen([sys.executable, '-m', 'sdhq_toolkit.gui', '--legacy'])
        self.status.set('Interface anterior aberta. O fluxo antigo mantém suas regras de workspace.')

    def start(self, build):
        if self.jobs.busy:
            raise ValueError('Aguarde ou cancele a operação atual.')
        values = {key: var.get().strip() for key, var in self.values.items()}
        for key in ('reference', 'folder', 'output', 'reports'):
            if not values[key]:
                raise ValueError('Preencha a localização: ' + key)
        folder = Path(values['folder']).resolve()
        reports = Path(values['reports']).resolve()
        if reports == folder or folder in reports.parents:
            raise ValueError('Escolha relatórios fora da pasta de alterações.')
        self.save()
        service = FolderRepackService(values['reference'], folder, values['game'] or None)
        operation = (lambda **kw: service.build(values['output'], **kw)) if build else service.preview
        self._launch_job(
            'Gerar GPK' if build else 'Conferir alterações',
            operation,
            reports,
            'Operação iniciada: lendo a referência e comparando os arquivos…',
        )

    def cancel(self):
        self.jobs.cancel()
        self.status.set('Cancelamento solicitado. Aguardando encerramento seguro…')

    def show_detail(self, *_):
        selection = self.table.selection()
        if selection:
            self.detail.configure(state='normal')
            self.detail.delete('1.0', 'end')
            self.detail.insert('end', '\n'.join(self.table.item(selection[0], 'values')))
            self.detail.configure(state='disabled')

    def poll(self):
        try:
            if self.jobs.progress:
                current, total, detail = self.jobs.progress
                self.jobs.progress = None
                self.bar.stop()
                self.bar.configure(mode='determinate', maximum=max(total, 1), value=current)
                self.status.set(f'{current}/{total}: {detail}')
            while True:
                event = self.jobs.events.get_nowait()
                if event[0] == 'log_error':
                    self.error('Não foi possível gravar relatório: ' + event[1])
                    continue
                _, name, status, result, report = event
                self.last_report = report
                self.bar.stop()
                for control in self.controls:
                    control.state(['!disabled'])
                self.cancel_button.state(['disabled'])
                if status in ('PASS', 'WARN'):
                    self.table.delete(*self.table.get_children())
                    for row in result.get('files', []):
                        if row['state'] != 'manter referência' or row['warnings']:
                            self.table.insert('', 'end', values=(row['path'], row['state'], '\n'.join(row['warnings'])))
                    operation = result.get('operation')
                    if operation == 'folder_preview':
                        text = f"Conferência concluída: {result['replacements']} substituições, {result['unchanged']} iguais, {result['retained']} mantidos da referência, {len(result['extras'])} novos não incluídos."
                    elif operation and operation.startswith('crio_'):
                        text = result.get('message', 'Operação CRio concluída')
                        if operation == 'crio_repack' and result.get('output'):
                            text += ': ' + result['output']
                    else:
                        text = result['message'] + ': ' + result['output']
                    self.status.set(text + f" Avisos: {len(result.get('warnings', []))}. Relatório: {report}")
                elif status == 'CANCELLED':
                    self.status.set('Operação cancelada. Nenhum arquivo incompleto foi publicado.')
                else:
                    self.error(f'{name}: {result}\nRelatório: {report}')
        except queue.Empty:
            pass
        except Exception as exc:
            self.error(exc)
        finally:
            if self.closing and not self.jobs.busy:
                self.root.destroy()
            else:
                self.root.after(100, self.poll)

    def close(self):
        self.guard(self.save)
        if self._theme_after:
            try:
                self.root.after_cancel(self._theme_after)
            except tk.TclError:
                pass
            self._theme_after = None
        self.closing = True
        if self.jobs.busy:
            self.cancel()


def main():
    root = tk.Tk()
    RepackApplication(root)
    root.mainloop()
