"""Desktop frontend for GARbro-assisted editing and reference repacking."""
import os
import queue
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .. import __version__
from ..core.folder_repack import FolderRepackService
from .controller import JobController
from .repack_controller import RepackSettings, garbro_status, launch_garbro
from .theme import apply_theme, add_header, WHITE, NAVY, LIGHT
from .background import ArtworkPanel
from .scroll_form import ScrollForm


class RepackApplication:
    def __init__(self, root):
        self.root = root
        root.title(f'Days ModToolkit {__version__} — School Days HQ / Shiny Days')
        root.geometry(f'{min(1460, root.winfo_screenwidth() - 60)}x{min(900, root.winfo_screenheight() - 100)}')
        root.minsize(760, 540)
        self.style = apply_theme(root)
        self.settings = RepackSettings(Path.cwd() / '.sdhq-repack.json')
        self.jobs = JobController()
        self.closing = False
        self.last_report = None
        self.controls = []
        self.artwork = ArtworkPanel(root)
        self.artwork.pack(side='right', fill='y', padx=(0, 12), pady=12)
        # Keep the tested content width when the user shrinks the window.
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
        self.panes.add(self.form, weight=1)
        frame = self.form.body
        results = ttk.Frame(self.panes, padding=8)
        self.panes.add(results, weight=1)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.header = add_header(frame, __version__)
        ttk.Label(frame, text='School Days HQ / Shiny Days — extraia no GARbro, edite e monte aqui.', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Use uma pasta exclusiva por GPK, preservando os caminhos internos e os formatos.', wraplength=880).pack(anchor='w', pady=(4, 12))
        fields = ttk.LabelFrame(frame, text='  01  /  Localizações  ', padding=10)
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
        ttk.Label(frame, textvariable=self.garbro_label).pack(anchor='w', pady=5)
        self.values['garbro'].trace_add('write', lambda *_: self.garbro_label.set(garbro_status(self.values['garbro'].get())))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', pady=8)
        for index, (label, callback) in enumerate([('Abrir GARbro', self.open_garbro), ('Conferir alterações', lambda: self.start(False)),
                                ('Gerar GPK', lambda: self.start(True)), ('Abrir saída', lambda: self.open_path('output')),
                                ('Relatórios', lambda: self.open_path('reports')), ('Interface anterior / .sdmod', self.legacy)]):
            button = ttk.Button(toolbar, text=label, command=lambda cb=callback: self.guard(cb),
                                style='Primary.TButton' if label == 'Gerar GPK' else 'TButton')
            button.grid(row=index // 3, column=index % 3, sticky='ew', padx=(0, 6), pady=3)
            toolbar.columnconfigure(index % 3, weight=1)
            self.controls.append(button)
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
        self.detail = tk.Text(results, height=2, wrap='word', state='disabled',
                              background=NAVY, foreground=WHITE, selectbackground=LIGHT, selectforeground=NAVY, relief='flat',
                              highlightthickness=1, highlightbackground=LIGHT, padx=8, pady=6)
        self.detail.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.table.bind('<<TreeviewSelect>>', self.show_detail)
        ttk.Label(frame, text='Avisos não bloqueiam a montagem; funcionamento no jogo não garantido.\nAntes de trocar o GPK em Packs, feche o jogo e o GARbro e guarde uma cópia do GPK anterior.', wraplength=1000).pack(anchor='w', pady=5)
        self.guard(self.load)
        self.form.enable_navigation()
        root.report_callback_exception = lambda kind, error, trace: self.error(error)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

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

    def save(self):
        self.settings.save({key: value.get().strip() for key, value in self.values.items()})

    def choose(self, key, file):
        def action():
            value = (filedialog.askopenfilename(parent=self.root, filetypes=[('Executável', '*.exe')] if key == 'garbro' else [('GPK', '*.gpk')])
                     if file else filedialog.askdirectory(parent=self.root))
            if value:
                self.values[key].set(value)
                self.save()
                self.status.set('Localização salva: ' + value)
            else:
                self.status.set('Seleção cancelada; localização anterior mantida.')
        self.guard(action)

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
        self.jobs.start('Gerar GPK' if build else 'Conferir alterações', operation, reports)
        for control in self.controls:
            control.state(['disabled'])
        self.cancel_button.state(['!disabled'])
        self.status.set('Operação iniciada: lendo a referência e comparando os arquivos…')
        self.bar.configure(mode='indeterminate')
        self.bar.start()

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
                    # Missing entries are summarized, not rendered as thousands of table rows.
                    for row in result.get('files', []):
                        if row['state'] != 'manter referência' or row['warnings']:
                            self.table.insert('', 'end', values=(row['path'], row['state'], '\n'.join(row['warnings'])))
                    if result['operation'] == 'folder_preview':
                        text = f"Conferência concluída: {result['replacements']} substituições, {result['unchanged']} iguais, {result['retained']} mantidos da referência, {len(result['extras'])} novos não incluídos."
                    else:
                        text = result['message'] + ': ' + result['output']
                    self.status.set(text + f" Avisos: {len(result['warnings'])}. Relatório: {report}")
                elif status == 'CANCELLED':
                    self.status.set('Operação cancelada. Nenhum GPK incompleto foi publicado.')
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
        self.closing = True
        if self.jobs.busy:
            self.cancel()


def main():
    root = tk.Tk()
    RepackApplication(root)
    root.mainloop()
