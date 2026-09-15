"""Optional artwork panel, configured without changing application code."""
import json
from pathlib import Path
import tkinter as tk

from .theme import WHITE, LIGHT


class ArtworkPanel(tk.Canvas):
    def __init__(self, root):
        super().__init__(root, background=LIGHT, highlightthickness=0, width=320)
        self.source = None
        self.pending = None
        self.options = {}
        try:
            config = Path.cwd() / 'tema.json'
            self.options = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
            from PIL import Image, ImageTk
            self.Image, self.ImageTk = Image, ImageTk
            path = Path(self.options.get('imagem', 'fundo.png'))
            if not path.is_absolute():
                path = Path.cwd() / path
            if path.is_file():
                with Image.open(path) as original:
                    self.source = original.convert('RGB')
        except Exception as exc:
            self.options = {}
            self.create_text(160, 80, text=f'Fundo indisponível:\n{exc}', width=290, fill='#17283B')
        self.bind('<Configure>', self.schedule)
        self.bind('<Destroy>', self.cleanup)

    def cleanup(self, event):
        if event.widget is self and self.pending:
            self.after_cancel(self.pending)
            self.pending = None

    def schedule(self, _=None):
        if self.pending:
            self.after_cancel(self.pending)
        self.pending = self.after(120, self.render)

    def render(self):
        self.pending = None
        if self.source is None:
            return
        try:
            width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
            opacity = max(0, min(1, float(self.options.get('opacidade', .4))))
            zoom = max(.2, min(3, float(self.options.get('zoom', 1))))
            dx, dy = float(self.options.get('x', 0)), float(self.options.get('y', 0))
            scale = max(width / self.source.width, height / self.source.height) * zoom
            # Sample the visible region directly, keeping memory bounded to the panel.
            left = (width - self.source.width * scale) / 2 + dx
            top = (height - self.source.height * scale) / 2 + dy
            picture = self.source.transform((width, height), self.Image.Transform.AFFINE,
                (1 / scale, 0, -left / scale, 0, 1 / scale, -top / scale),
                resample=self.Image.Resampling.BICUBIC, fillcolor=WHITE)
            picture = self.Image.blend(self.Image.new('RGB', (width, height), WHITE), picture, opacity)
            self.photo = self.ImageTk.PhotoImage(picture, master=self)
            self.delete('all')
            self.create_image(0, 0, image=self.photo, anchor='nw')
        except Exception as exc:
            self.delete('all')
            self.create_text(160, 80, text=f'Confira tema.json:\n{exc}', width=290, fill='#17283B')
