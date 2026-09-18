"""Native ttk desktop shell. Widgets delegate operations to application services."""
from __future__ import annotations

import json
import os
import queue
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import __version__
from ..core.desktop import DesktopService, Settings, STATES
from ..core import mods
from .controller import JobController, filter_rows, resolve_selection


class Application:
    PAGE_SIZE = 500

    def __init__(self, root):
        self.root = root
        self.jobs = JobController()
        self.service = None
        self.rows, self.filtered = [], []
        self.marked = set()
        self.folders = {}
        self.tree_files = {}
        self.folder_contents = {}
        self.populated_folders = set()
        self.page = 0
        self.callbacks = {}
        self.closing = False
        self.preview = None
        self.action_buttons = {}
        self.tree_scope = ()
        self.allow_unknown = tk.BooleanVar(value=False)
        self.compatibility_mode = tk.StringVar(value="Estrito")
        self.config_path = Path(__file__).resolve().parents[3] / ".sdhq-desktop.json"
        self.root.title(f"School Days HQ / Shiny Days · Modding Toolkit {__version__}")
        self.root.geometry("1380x900")
        self.root.minsize(1060, 720)
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        else:
            style.theme_use("clam")
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 5))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Subtitle.TLabel", foreground="#526579")
        shell = ttk.Frame(root, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="School Days HQ / Shiny Days", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text=f"MODDING TOOLKIT  /  {__version__}  /  SDHQ v1.02 + Shiny Days 1.01e", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        self.config_tab = ttk.Frame(self.tabs, padding=14)
        self.explorer = ttk.Frame(self.tabs, padding=10)
        self.mods_tab = ttk.Frame(self.tabs, padding=14)
        self.log_tab = ttk.Frame(self.tabs, padding=10)
        for frame, title in ((self.config_tab, "Localizações"), (self.explorer, "Arquivos e GPKs"), (self.mods_tab, "Pacotes .sdmod"), (self.log_tab, "Logs e relatórios")):
            self.tabs.add(frame, text=title)
        self.paths = {}
        defaults = dict(game=str(Path.cwd().parent), packs=str(Path.cwd().parent / "Packs"),
                        workspace=str(Path.cwd() / "workspace"), reports=str(Path.cwd() / "reports"), output=str(Path.cwd() / "output_v011"))
        try:
            defaults.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        for index, (key, label) in enumerate((("game", "Instalação do jogo"), ("packs", "Packs originais"), ("workspace", "Workspace de edição"), ("reports", "Logs e relatórios"), ("output", "Saída de GPKs e pacotes"))):
            variable = tk.StringVar(value=defaults[key])
            self.paths[key] = variable
            ttk.Label(self.config_tab, text=label).grid(row=index, column=0, sticky="w", padx=(0, 15), pady=10)
            ttk.Entry(self.config_tab, textvariable=variable).grid(row=index, column=1, sticky="ew")
            ttk.Button(self.config_tab, text="Procurar…", command=lambda k=key: self.choose_path(k)).grid(row=index, column=2, padx=8)
        self.config_tab.columnconfigure(1, weight=1)
        ttk.Label(self.config_tab, text="Use os GPKs originais como referência. A saída é sempre separada de Packs.\nA detecção lê os índices; não exige extração completa nem altera a instalação.", style="Subtitle.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=18)
        self.detect_button = ttk.Button(self.config_tab, text="Detectar GPKs e abrir workspace", command=self.detect)
        self.detect_button.grid(row=7, column=1, sticky="w")
        self.build_explorer()
        self.build_mods()
        log_buttons = ttk.Frame(self.log_tab)
        log_buttons.pack(fill="x")
        ttk.Button(log_buttons, text="Abrir pasta de relatórios", command=lambda: self.open_external(Path(self.paths["reports"].get()))).pack(side="left")
        ttk.Button(log_buttons, text="Abrir último relatório", command=lambda: self.open_external(getattr(self, "last_report", None))).pack(side="left", padx=8)
        self.log = tk.Text(self.log_tab, wrap="word", font=("Consolas", 10), state="disabled")
        self.log.pack(fill="both", expand=True, pady=10)
        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(10, 0))
        self.status = tk.StringVar(value="Selecione as localizações e detecte os GPKs para começar.")
        ttk.Label(self.config_tab, textvariable=self.status, wraplength=850).grid(row=8, column=0, columnspan=3, sticky="w", pady=16)
        self.explorer_status.configure(textvariable=self.status)
        ttk.Label(footer, textvariable=self.status).pack(side="left", fill="x", expand=True)
        self.bar = ttk.Progressbar(footer, length=190)
        self.bar.pack(side="left", padx=12)
        self.cancel_button = ttk.Button(footer, text="Cancelar", command=self.cancel)
        self.cancel_button.pack(side="right")
        self.cancel_button.state(["disabled"])
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        root.after(100, self.poll)

    def choose_path(self, key):
        path = filedialog.askdirectory(title="Selecionar " + key, mustexist=key in ("game", "packs"))
        if path:
            self.paths[key].set(path)
            if key == "game":
                self.paths["packs"].set(str(Path(path) / "Packs"))

    def build_explorer(self):
        toolbar = ttk.Frame(self.explorer)
        toolbar.pack(fill="x")
        for index, (label, command) in enumerate((("Extrair seleção", lambda: self.extract()), ("Extrair tudo", lambda: self.extract(True)),
                               ("Atualizar / validar", self.refresh), ("Repack GPKs selecionados", self.repack),
                               ("Restaurar arquivo", self.restore), ("Abrir arquivo", self.open_file), ("Abrir pasta", lambda: self.open_file(True)),
                               ("Repack todos os GPKs", lambda: self.repack(True)))):
            button = ttk.Button(toolbar, text=label, command=command)
            button.grid(row=index // 4, column=index % 4, sticky="ew", padx=(0, 5), pady=2)
            self.action_buttons[label] = button
        for index in range(4):
            toolbar.columnconfigure(index, weight=1)
        self.explorer_status = ttk.Label(self.explorer, wraplength=1100, style="Subtitle.TLabel")
        self.explorer_status.pack(fill="x", pady=(6, 0))
        self.selection_text = tk.StringVar(value="Selecione um GPK ou uma pasta na árvore, ou arquivos na lista.")
        ttk.Label(self.explorer, textvariable=self.selection_text, wraplength=1100).pack(fill="x", pady=(4, 0))
        filters = ttk.Frame(self.explorer)
        filters.pack(fill="x", pady=10)
        self.query, self.ext, self.kind, self.state = (tk.StringVar() for _ in range(4))
        ttk.Label(filters, text="Pesquisar").pack(side="left")
        search = ttk.Entry(filters, textvariable=self.query, width=32)
        search.pack(side="left", padx=6)
        search.bind("<Return>", lambda _: self.filter())
        self.filter_boxes = []
        for label, variable, width in (("Extensão", self.ext, 10), ("Formato", self.kind, 14), ("Estado", self.state, 14)):
            ttk.Label(filters, text=label).pack(side="left", padx=(8, 3))
            box = ttk.Combobox(filters, textvariable=variable, width=width, state="readonly")
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda _: self.filter())
            self.filter_boxes.append(box)
        ttk.Button(filters, text="Filtrar", command=self.filter).pack(side="left", padx=6)
        ttk.Button(filters, text="Limpar", command=self.clear_filter).pack(side="left")
        options = ttk.Frame(self.explorer)
        options.pack(fill="x", pady=(0, 6))
        ttk.Label(options, text="Validação / repack:").pack(side="left")
        mode = ttk.Combobox(options, textvariable=self.compatibility_mode,
                            values=("Estrito", "Experimental"), state="readonly", width=15)
        mode.pack(side="left", padx=8)
        unknown = ttk.Checkbutton(options, text="Permitir formatos desconhecidos", variable=self.allow_unknown)
        unknown.pack(side="left", padx=8)
        self.action_buttons["Modo de compatibilidade"] = mode
        self.action_buttons["Formatos desconhecidos"] = unknown
        ttk.Label(self.explorer, text="Experimental: mantém os bytes editados e trata problemas de formato como avisos; não garante compatibilidade no jogo.",
                  wraplength=1050, style="Subtitle.TLabel").pack(fill="x", pady=(0, 6))
        paned = ttk.Panedwindow(self.explorer, orient="horizontal")
        self.browser_panes = paned
        paned.pack(fill="both", expand=True)
        left, right = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=4)
        ttk.Label(left, text="GPKs, pastas e arquivos • Ctrl / Shift").pack(anchor="w", pady=(0, 6))
        ttk.Button(left, text="Mostrar painel de arquivos →", command=self.show_file_panel).pack(anchor="w", pady=(0, 6))
        self.tree = ttk.Treeview(left, show="tree", selectmode="extended")
        self.add_scroll(left, self.tree)
        self.tree.bind("<<TreeviewSelect>>", self.tree_selected)
        self.tree.bind("<<TreeviewOpen>>", self.tree_opened)
        self.tree.bind("<Double-1>", self.tree_double_click)
        ttk.Label(right, text="Arquivos da seleção (inclui subpastas)").pack(anchor="w", pady=(0, 6))
        self.empty_list_text = tk.StringVar()
        ttk.Label(right, textvariable=self.empty_list_text, wraplength=650, style="Subtitle.TLabel").pack(fill="x")
        self.table = ttk.Treeview(right, columns=("marked", "path", "format", "state", "size"), show="headings", selectmode="extended", height=12)
        for key, title, width in (("marked", "✓", 35), ("path", "GPK / caminho", 420), ("format", "Formato", 95), ("state", "Estado", 110), ("size", "Bytes", 90)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, stretch=key == "path")
        for state, color in (("modificado", "#164d93"), ("inválido", "#aa2020"), ("ausente", "#aa2020"), ("não extraído", "#687887"), ("novo", "#995900")):
            self.table.tag_configure(state, foreground=color)
        table_frame = ttk.Frame(right)
        table_frame.pack(fill="both", expand=True)
        self.table.pack(in_=table_frame, side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<Double-1>", lambda _: self.details())
        self.table.bind("<<TreeviewSelect>>", lambda _: self.update_selection_text())
        nav = ttk.Frame(right)
        nav.pack(fill="x", pady=6)
        for label, command in (("◀", lambda: self.change_page(-1)), ("▶", lambda: self.change_page(1)),
                               ("Marcar seleção", self.mark), ("Marcar filtrados", self.mark_filtered),
                               ("Limpar marcas", self.clear_marks), ("Especificações", self.details)):
            button = ttk.Button(nav, text=label, command=command)
            button.pack(side="left", padx=2)
            if label == "Especificações":
                self.action_buttons[label] = button
        self.count = tk.StringVar()
        ttk.Label(right, textvariable=self.count).pack(anchor="w")
        self.detail_text = tk.Text(right, height=9, wrap="word", font=("Consolas", 10), state="disabled")
        self.detail_text.pack(fill="x", pady=(8, 0))
        ttk.Label(self.explorer, text="Operações usam marcas, depois arquivos selecionados, depois GPKs/pastas da árvore. Repack inclui todas as alterações dos GPKs selecionados.", style="Subtitle.TLabel").pack(anchor="w", pady=(8, 0))

    def show_file_panel(self):
        self.browser_panes.update_idletasks()
        width = self.browser_panes.winfo_width()
        if width > 1:
            self.browser_panes.sashpos(0, max(220, int(width * 0.30)))

    def populate_folder(self, node):
        if node not in self.folders or node in self.populated_folders:
            return
        for child in self.tree.get_children(node):
            if "placeholder" in self.tree.item(child, "tags"):
                self.tree.delete(child)
        archive, folder = self.folders[node]
        for relative in self.folder_contents.get((archive, folder), []):
            leaf = self.tree.insert(node, "end", text=relative.rsplit("/", 1)[-1], tags=("file",))
            self.tree_files[leaf] = (archive, relative)
        self.populated_folders.add(node)

    def tree_opened(self, _event=None):
        self.populate_folder(self.tree.focus())

    def tree_double_click(self, event):
        node = self.tree.identify_row(event.y)
        if node in self.tree_files:
            self.tree.selection_set(node)
            self.tree_selected()
            self.details()

    def tree_filter_scope(self):
        scope = []
        for node in self.tree.selection():
            if node in self.folders:
                scope.append(self.folders[node])
            elif node in self.tree_files:
                archive, relative = self.tree_files[node]
                scope.append((archive, relative.rpartition("/")[0]))
        return list(dict.fromkeys(scope))

    def tree_selection_signature(self):
        return tuple(("folder", *self.folders[node]) if node in self.folders else ("file", *self.tree_files[node])
                     for node in self.tree.selection() if node in self.folders or node in self.tree_files)

    @staticmethod
    def add_scroll(parent, tree):
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.configure(yscrollcommand=scroll.set)

    def build_mods(self):
        self.project = tk.StringVar()
        self.package_path = tk.StringVar()
        self.mod_id = tk.StringVar()
        for index, (label, variable, command) in enumerate((("Projeto .sdmod", self.project, self.choose_project), ("Pacote .sdmod", self.package_path, self.choose_package))):
            ttk.Label(self.mods_tab, text=label).grid(row=index, column=0, sticky="w", pady=8)
            ttk.Entry(self.mods_tab, textvariable=variable).grid(row=index, column=1, sticky="ew", padx=12)
            ttk.Button(self.mods_tab, text="Selecionar…", command=command).grid(row=index, column=2)
        self.mods_tab.columnconfigure(1, weight=1)
        actions = ttk.Frame(self.mods_tab)
        actions.grid(row=2, column=0, columnspan=3, sticky="w", pady=12)
        for label, command in (("Novo projeto", self.new_project), ("Prévia exata", self.preview_package), ("Criar pacote da prévia", self.build_package), ("Inspecionar pacote", self.inspect_package), ("Aplicar no workspace", self.apply_package)):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))
        remove = ttk.Frame(self.mods_tab)
        remove.grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Label(remove, text="ID do mod instalado").pack(side="left")
        self.installed = ttk.Combobox(remove, textvariable=self.mod_id, width=35)
        self.installed.pack(side="left", padx=10)
        ttk.Button(remove, text="Listar instalados", command=self.list_mods).pack(side="left")
        ttk.Button(remove, text="Remover e restaurar", command=self.remove_package).pack(side="left", padx=6)
        ttk.Checkbutton(self.mods_tab, text="Permitir arquivos de formato desconhecido (pacote e repack; compatibilidade não verificada)", variable=self.allow_unknown).grid(row=4, column=0, columnspan=3, sticky="w", pady=12)
        self.package_text = tk.Text(self.mods_tab, wrap="none", font=("Consolas", 10), state="disabled")
        self.package_text.grid(row=5, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(self.mods_tab, orient="vertical", command=self.package_text.yview)
        scroll.grid(row=5, column=2, sticky="ns")
        self.package_text.configure(yscrollcommand=scroll.set)
        self.mods_tab.rowconfigure(5, weight=1)

    def set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        widget.configure(state="disabled")

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self, name, operation, callback=None, require_service=True):
        if not self.ready(require_service):
            return
        reports = self.service.settings.reports if self.service else Path(self.paths["reports"].get()).resolve()
        packs = Path(self.paths["packs"].get()).resolve()
        if reports == packs or packs in reports.parents:
            messagebox.showerror("Relatórios", "A pasta de relatórios deve ficar fora de Packs.")
            return
        self.callbacks[name] = callback
        self.status.set(name + "…")
        self.write_log(name + ": iniciada")
        self.detect_button.state(["disabled"])
        for button in self.action_buttons.values():
            button.state(["disabled"])
        self.bar.configure(mode="indeterminate")
        self.bar.start(15)
        self.cancel_button.state(["!disabled"])
        self.jobs.start(name, operation, reports)

    def ready(self, require_service=True):
        if self.jobs.busy:
            messagebox.showinfo("Operação em andamento", "Aguarde a operação atual ou clique em Cancelar antes de iniciar outra.")
            return False
        if require_service and (self.service is None or not self.service.indexes):
            messagebox.showinfo("Detectar GPKs", "Configure as localizações e detecte os GPKs primeiro.")
            return False
        return True

    def detect(self):
        if self.jobs.busy:
            return
        try:
            settings = Settings(**{key: Path(value.get()) for key, value in self.paths.items()})
            candidate = DesktopService(settings)
            self.config_path.write_text(json.dumps({key: value.get() for key, value in self.paths.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Localizações", str(exc))
            return
        self.service = candidate
        self.marked.clear()
        self.preview = None
        self.run("Detectar GPKs", candidate.detect, self.accept_rows, require_service=False)

    def accept_rows(self, rows):
        selected_folders = {self.folders[node] for node in self.tree.selection() if node in self.folders}
        selected_tree_files = {self.tree_files[node] for node in self.tree.selection() if node in self.tree_files}
        opened = {value for node, value in self.folders.items() if self.tree.item(node, "open")}
        selected_files = set(self.selected_files())
        old_page = self.page
        self.rows = rows
        self.marked.intersection_update((r["archive"], r["path"]) for r in rows)
        self.tree.delete(*self.tree.get_children())
        self.folders = {}
        self.tree_files = {}
        self.folder_contents = {}
        self.populated_folders = set()
        nodes = {}
        for archive in self.service.archives:
            node = self.tree.insert("", "end", text=archive + ".gpk", open=False)
            nodes[(archive, "")] = node
            self.folders[node] = (archive, "")
        folders = set()
        for row in rows:
            self.folder_contents.setdefault((row["archive"], row["path"].rpartition("/")[0]), []).append(row["path"])
            parts = row["path"].split("/")[:-1]
            for index in range(1, len(parts) + 1):
                folders.add((row["archive"], "/".join(parts[:index])))
        for archive, folder in sorted(folders):
            parent = folder.rpartition("/")[0]
            node = self.tree.insert(nodes[(archive, parent)], "end", text=folder.rsplit("/", 1)[-1])
            nodes[(archive, folder)] = node
            self.folders[node] = (archive, folder)
        for box, values in zip(self.filter_boxes, (sorted({r["extension"] for r in rows}), sorted({r["format"] for r in rows}), STATES)):
            box["values"] = [""] + list(values)
        for node, value in self.folders.items():
            if self.folder_contents.get(value):
                self.tree.insert(node, "end", text="Carregando arquivos…", tags=("placeholder",))
            if value in opened:
                self.populate_folder(node)
                self.tree.item(node, open=True)
        for archive, relative in selected_tree_files:
            parent = nodes.get((archive, relative.rpartition("/")[0]))
            if parent:
                self.populate_folder(parent)
        self.tree.selection_set([node for node, value in self.folders.items() if value in selected_folders]
                                + [node for node, value in self.tree_files.items() if value in selected_tree_files])
        self.filter()
        self.page = min(old_page, max(0, (len(self.filtered) - 1) // self.PAGE_SIZE))
        if self.page:
            self.render_page()
        self.table.selection_set([str(index) for index in range(self.page * self.PAGE_SIZE, min(len(self.filtered), (self.page + 1) * self.PAGE_SIZE))
                                  if (self.filtered[index]["archive"], self.filtered[index]["path"]) in selected_files])
        self.update_selection_text()
        self.tabs.select(self.explorer)

    def tree_selected(self, _event=None):
        scope = self.tree_selection_signature()
        if scope != self.tree_scope:
            self.filter()
            files = {self.tree_files[node] for node in self.tree.selection() if node in self.tree_files}
            has_folders = any(node in self.folders for node in self.tree.selection())
            matches = [i for i, row in enumerate(self.filtered) if (row["archive"], row["path"]) in files]
            if matches and not has_folders:
                self.page = matches[0] // self.PAGE_SIZE
                self.render_page()
                visible = set(self.table.get_children())
                if len(files) == 1:
                    self.table.selection_set([str(index) for index in matches if str(index) in visible])
                self.table.see(str(matches[0]))
            self.update_selection_text()

    def filter(self):
        scope = self.tree_filter_scope() or None
        self.tree_scope = self.tree_selection_signature()
        self.filtered = filter_rows(self.rows, self.query.get(), self.ext.get(), self.kind.get(), self.state.get(), scope)
        self.page = 0
        self.render_page()

    def render_page(self):
        self.table.delete(*self.table.get_children())
        self.empty_list_text.set("" if self.filtered else "Nenhum arquivo corresponde à seleção e aos filtros. Use Limpar para remover os filtros.")
        for index in range(self.page * self.PAGE_SIZE, min(len(self.filtered), (self.page + 1) * self.PAGE_SIZE)):
            row = self.filtered[index]
            self.table.insert("", "end", iid=str(index), values=("✓" if (row["archive"], row["path"]) in self.marked else "", f"{row['archive']}/{row['path']}", row["format"], row["state"], f"{row['size']:,}"), tags=(row["state"],))
        modified = [r for r in self.rows if r["state"] in ("modificado", "inválido")]
        affected = sorted({r["archive"] for r in modified})
        pending = sum(r["state"] == "não verificado" for r in self.rows)
        summary = (f"{pending:,} arquivos aguardam Atualizar / validar; alterações ainda não verificadas" if pending
                   else f"{len(modified)} alterados • GPKs afetados: {', '.join(affected) or 'nenhum'}")
        self.count.set(f"{len(self.filtered):,} arquivos • página {self.page + 1}/{max(1, (len(self.filtered) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)} • {len(self.marked)} marcados\n{summary}")
        self.update_selection_text()

    def change_page(self, delta):
        self.page = max(0, min(self.page + delta, max(0, (len(self.filtered) - 1) // self.PAGE_SIZE)))
        self.render_page()

    def clear_filter(self):
        for variable in (self.query, self.ext, self.kind, self.state):
            variable.set("")
        self.tree.selection_remove(*self.tree.selection())
        self.filter()

    def table_selected_files(self):
        return [(self.filtered[int(i)]["archive"], self.filtered[int(i)]["path"]) for i in self.table.selection()
                if i.isdigit() and int(i) < len(self.filtered)]

    def selected_files(self):
        return self.table_selected_files() or [self.tree_files[node] for node in self.tree.selection() if node in self.tree_files]

    def mark(self):
        self.marked.update(self.selected_files())
        self.render_page()

    def mark_filtered(self):
        self.marked.update((r["archive"], r["path"]) for r in self.filtered)
        self.render_page()

    def clear_marks(self):
        self.marked.clear()
        self.render_page()

    def selection(self, all_files=False):
        files = self.marked or set(self.table_selected_files())
        folders = []
        if not files:
            files = {self.tree_files[node] for node in self.tree.selection() if node in self.tree_files}
            folders = [self.folders[node] for node in self.tree.selection() if node in self.folders]
        return resolve_selection(self.rows, files, folders, all_files)

    def update_selection_text(self):
        selection = self.selection()
        source = "Marcas" if self.marked else ("Lista" if self.table.selection() else "Árvore")
        count = sum(len(paths) for paths in selection.values())
        self.selection_text.set(f"{source}: {count:,} arquivos selecionados • GPKs: {', '.join(selection) or 'nenhum'}")

    def require_selection(self, all_files=False):
        if not self.ready():
            return None
        selection = self.selection(all_files)
        if not selection:
            messagebox.showinfo("Nenhuma seleção", "Selecione o nome de um GPK ou uma pasta na árvore à esquerda, ou arquivos na lista. Para todos os GPKs, use o botão de operação completa.")
            return None
        return selection

    def refresh(self):
        if not self.ready():
            return
        names = list(self.selection()) or None
        mode = "experimental" if self.compatibility_mode.get() == "Experimental" else "strict"
        allow = self.allow_unknown.get()
        self.run("Atualizar e validar", lambda **kw: self.service.validate(names=names, compatibility_mode=mode, allow_unknown=allow, **kw), self.validation_completed)

    def validation_completed(self, report):
        self.accept_rows(self.service.rows)
        result = "BLOQUEADO" if not report["can_repack"] else ("COM AVISOS" if report["warning_count"] else "APROVADO")
        lines = [f"Validação: {result} • Modo: {report['compatibility_mode']}",
                 f"{report['checked']} arquivos verificados; {report['modified']} alterados; {report['invalid']} com problemas de formato.",
                 f"{report['blocking_count']} bloqueio(s); {report['warning_count']} aviso(s).",
                 "Geração do GPK permitida neste modo." if report["can_repack"] else "O repack não será gerado até resolver os bloqueios ou escolher um modo adequado."]
        for title, items in (("BLOQUEIOS", report["errors"]), ("AVISOS", report["warnings"])):
            if items:
                lines.extend(["", title])
                lines.extend(f"{item['archive']}/{item['path']}: {item['reason']}" for item in items)
        if report["compatibility_mode"] == "experimental":
            lines.extend(["", "Experimental preserva o conteúdo editado; não corrige automaticamente arquivos nem comprova funcionamento no jogo."])
        self.set_text(self.detail_text, "\n".join(lines))
        self.status.set(f"Validação {result}: {report['modified']} alterados, {report['blocking_count']} bloqueios, {report['warning_count']} avisos.")

    def extract(self, all_files=False):
        selection = self.require_selection(all_files)
        if selection:
            self.run("Extrair arquivos", lambda **kw: self.service.extract(selection, **kw), self.extraction_completed)

    def extraction_completed(self, result):
        self.accept_rows(self.service.rows)
        lines = [f"{item['archive']}.gpk: {item['newly_extracted']} extraídos agora, "
                 f"{item['already_extracted']} já extraídos (preservados), {item['restored']} restaurados.\n"
                 f"Pasta: {item['destination']}" for item in result]
        summary = "\n\n".join(lines)
        self.set_text(self.detail_text, summary)
        self.status.set("Concluído. Os arquivos estão no workspace; nenhuma validação global foi iniciada.")
        self.write_log(summary)

    def repack(self, all_files=False):
        selection = self.require_selection(all_files)
        if selection:
            allow = self.allow_unknown.get()
            mode = "experimental" if self.compatibility_mode.get() == "Experimental" else "strict"
            self.run("Repack", lambda **kw: self.service.repack(selection, allow_unknown=allow, compatibility_mode=mode, **kw), self.repack_completed)

    def repack_completed(self, result):
        self.accept_rows(self.service.rows)
        self.set_text(self.detail_text, result)
        warning = " com avisos de compatibilidade" if any(item.get("status") == "WARN" for item in result) else ""
        output = Path(result[0]["output"]).parent if result else self.service.settings.output
        self.status.set(f"Repack concluído{warning}: {len(result)} GPK(s) em {output}")

    def one_file(self):
        files = self.selected_files()
        if len(files) != 1:
            messagebox.showinfo("Selecionar arquivo", "Selecione um arquivo na lista ou dentro de uma pasta da árvore.")
            return None
        return files[0]

    def restore(self):
        if not self.ready():
            return
        item = self.one_file()
        if item and self.service and not self.jobs.busy:
            if messagebox.askyesno("Restaurar original", f"Substituir {item[0]}/{item[1]} pelo arquivo do GPK original? As edições deste arquivo serão descartadas."):
                self.run("Restaurar arquivo", lambda **kw: self.service.extract({item[0]: [item[1]]}, restore=True, **kw), self.extraction_completed)

    def details(self):
        if not self.ready():
            return
        item = self.one_file()
        if item and self.service:
            self.run("Especificações", lambda cancel, progress: self.service.inspect(*item, cancel=cancel), lambda result: self.set_text(self.detail_text, result))

    def open_external(self, path):
        if path is None or not path.exists():
            messagebox.showinfo("Abrir", "O arquivo ou a pasta ainda não existe. Extraia o arquivo antes de abrir.")
            return
        try:
            os.startfile(str(path.resolve()))
        except (OSError, AttributeError) as exc:
            messagebox.showerror("Abrir", str(exc))

    def open_file(self, folder=False):
        if not self.ready():
            return
        if folder and not self.table.selection() and self.tree.selection() and self.tree.selection()[0] in self.folders:
            archive, relative = self.folders[self.tree.selection()[0]]
            self.open_external(self.service.file_path(archive, relative))
            return
        item = self.one_file()
        if item:
            path = self.service.file_path(*item)
            self.open_external(path.parent if folder else path)

    def choose_project(self):
        path = filedialog.askdirectory(title="Projeto com mod.json")
        if path:
            self.project.set(path)
            self.preview = None

    def choose_package(self):
        path = filedialog.askopenfilename(filetypes=[("School Days mod", "*.sdmod")])
        if path:
            self.package_path.set(path)

    def new_project(self):
        if self.jobs.busy:
            return
        directory = filedialog.askdirectory(title="Pasta vazia para o novo projeto", mustexist=False)
        if not directory:
            return
        fields = {}
        for key, prompt, initial in (("mod_id", "ID (ex.: autor.meu-mod)", ""), ("name", "Nome do mod", ""), ("author", "Autor", ""), ("version", "Versão", "1.0.0")):
            answer = simpledialog.askstring("Novo projeto", prompt, initialvalue=initial)
            if not answer:
                return
            fields[key] = answer
        self.project.set(directory)
        self.run("Criar projeto", lambda **_: mods.create_mod_project(Path(directory), **fields), lambda r: self.set_text(self.package_text, r), require_service=False)

    def preview_package(self):
        project, allow = Path(self.project.get()), self.allow_unknown.get()
        def accepted(result):
            self.preview = (project, result["files"], allow)
            self.set_text(self.package_text, result)
        self.run("Prévia do pacote", lambda **kw: self.service.package(project, allow_unknown=allow, **kw), accepted)

    def build_package(self):
        if not self.preview:
            messagebox.showinfo("Prévia necessária", "Gere a prévia exata antes de criar o pacote.")
            return
        project, expected, allow = self.preview
        if project != Path(self.project.get()) or allow != self.allow_unknown.get():
            messagebox.showinfo("Atualizar prévia", "O projeto ou as opções mudaram. Gere uma nova prévia.")
            return
        self.run("Criar pacote", lambda **kw: self.service.package(project, preview=False, expected=expected, allow_unknown=allow, **kw), lambda r: self.set_text(self.package_text, r))

    def inspect_package(self):
        path = Path(self.package_path.get())
        def inspect(cancel, progress):
            def callback(*args):
                cancel.check()
                progress(*args)
            return mods.inspect_mod_package(path, progress=callback)
        self.run("Inspecionar pacote", inspect, lambda r: self.set_text(self.package_text, r), require_service=False)

    def apply_package(self):
        path = Path(self.package_path.get())
        self.run("Aplicar pacote", lambda **kw: self.service.apply_package(path, **kw), lambda r: self.package_changed(r))

    def remove_package(self):
        mod_id = self.mod_id.get()
        self.run("Remover pacote", lambda **kw: self.service.remove_package(mod_id, **kw), lambda r: self.package_changed(r))

    def package_changed(self, result):
        self.set_text(self.package_text, result)
        # Reload metadata only; do not launch an implicit whole-workspace validation.
        self.run("Atualizar catálogo", self.service.catalog, self.accept_rows)

    def list_mods(self):
        def accepted(result):
            self.installed["values"] = [item["id"] for item in result if item.get("installed")]
            self.set_text(self.package_text, result)
        self.run("Listar mods", lambda **_: self.service.installed_mods(), accepted)

    def cancel(self):
        self.jobs.cancel()
        self.status.set("Cancelamento solicitado; aguardando um ponto seguro…")

    def close(self):
        if self.jobs.busy:
            self.closing = True
            self.cancel()
        else:
            self.root.destroy()

    def callback_error(self, kind, value, tb):
        details = "".join(traceback.format_exception(kind, value, tb))
        self.write_log(details)
        self.status.set("Falha na interface; consulte Logs e relatórios.")
        messagebox.showerror("Erro na interface", str(value))

    def poll(self):
        try:
            self.poll_events()
        except Exception as exc:
            self.callback_error(type(exc), exc, exc.__traceback__)
        finally:
            if self.closing and not self.jobs.busy:
                self.root.destroy()
            else:
                self.root.after(100, self.poll)

    def poll_events(self):
        if self.jobs.progress:
            current, total, detail = self.jobs.progress
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self.bar["value"] = current / max(1, total) * 100
            self.status.set(f"{current:,}/{total:,} • {detail[:95]}")
            self.jobs.progress = None
        # Consume completion only after worker exits, so callbacks may start a new job.
        if not self.jobs.busy:
            try:
                while True:
                    event = self.jobs.events.get_nowait()
                    if event[0] == "log_error":
                        self.write_log("Falha ao gravar relatório: " + event[1])
                        continue
                    _, name, status, result, report = event
                    self.bar.stop()
                    self.detect_button.state(["!disabled"])
                    for button in self.action_buttons.values():
                        button.state(["!disabled"])
                    self.cancel_button.state(["disabled"])
                    self.status.set(f"{name}: {status}")
                    self.write_log(f"{name}: {status}" + (f"\n{result}" if status != "PASS" else "") + f"\nRelatório: {report}")
                    self.last_report = report
                    callback = self.callbacks.pop(name, None)
                    if not self.closing:
                        if isinstance(result, dict) and result.get("operation") == "asset_validation":
                            self.validation_completed(result)
                        elif status in ("PASS", "WARN") and callback:
                            callback(result)
                        elif status == "FAIL":
                            messagebox.showerror(name, str(result)[:5000])
                    if self.jobs.busy:
                        break
            except queue.Empty:
                pass


def main():
    from .repack_app import main as repack_main
    repack_main()
