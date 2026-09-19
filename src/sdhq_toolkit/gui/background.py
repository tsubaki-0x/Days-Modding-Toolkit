"""Game-specific artwork panel for the Days ModToolkit."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .theme import DEFAULT_THEME_ID, load_theme_profile, palette


class ArtworkPanel(tk.Canvas):
    def __init__(self, root, theme_id: str = DEFAULT_THEME_ID):
        # Do not use the name _root here: tkinter.Misc already defines
        # a private _root() method that event dispatch and exception handling call.
        # Shadowing it with a Tk instance makes Tkinter crash with
        # TypeError: 'Tk' object is not callable (notably visible on Python 3.14).
        self._host_root = root
        self.theme_id = theme_id
        self.profile = load_theme_profile(theme_id, allow_root_override=(theme_id == DEFAULT_THEME_ID))
        colors = palette(self.profile)
        super().__init__(root, background=colors['light'], highlightthickness=0, width=320)
        self.source = None
        self.native_source = None
        self.photo = None
        self.pending = None
        self.options = {}
        self.Image = None
        self.ImageTk = None
        self.set_theme(theme_id)
        self.bind('<Configure>', self.schedule)

    def destroy(self):
        if self.pending:
            try:
                self._host_root.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None
        super().destroy()

    def set_theme(self, theme_id: str):
        self.theme_id = theme_id
        self.profile = load_theme_profile(theme_id, allow_root_override=(theme_id == DEFAULT_THEME_ID))
        self.options = self.profile
        colors = palette(self.profile)
        self.configure(background=colors['light'])
        self.source = None
        self.native_source = None
        self.photo = None
        path = Path(self.profile.get('_image_path', ''))
        try:
            if path.is_file():
                try:
                    from PIL import Image, ImageTk
                    self.Image, self.ImageTk = Image, ImageTk
                    with Image.open(path) as original:
                        self.source = original.convert('RGB')
                except ImportError:
                    self.native_source = tk.PhotoImage(master=self, file=str(path))
        except Exception as exc:
            self.delete('all')
            self.create_text(160, 80, text=f'Arte indisponível:\n{exc}', width=290, fill=colors['ink'])
        self.schedule()

    def schedule(self, _=None):
        if self.pending:
            self._host_root.after_cancel(self.pending)
        self.pending = self._host_root.after(80, self.render)

    def render(self):
        self.pending = None
        if self.source is None and self.native_source is None:
            return
        colors = palette(self.profile)
        try:
            width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
            dx, dy = float(self.options.get('x', 0)), float(self.options.get('y', 0))
            if self.source is None:
                self.delete('all')
                self.create_image(width / 2 + dx, height / 2 + dy,
                                  image=self.native_source, anchor='center')
                return

            opacity = max(0, min(1, float(self.options.get('opacidade', 1.0))))
            zoom = max(.2, min(3, float(self.options.get('zoom', 1))))
            scale = max(width / self.source.width, height / self.source.height) * zoom
            left = (width - self.source.width * scale) / 2 + dx
            top = (height - self.source.height * scale) / 2 + dy
            picture = self.source.transform(
                (width, height),
                self.Image.Transform.AFFINE,
                (1 / scale, 0, -left / scale, 0, 1 / scale, -top / scale),
                resample=self.Image.Resampling.BICUBIC,
                fillcolor=colors['white'],
            )
            if opacity < 1.0:
                picture = self.Image.blend(
                    self.Image.new('RGB', (width, height), colors['white']), picture, opacity
                )
            self.photo = self.ImageTk.PhotoImage(picture, master=self)
            self.delete('all')
            self.create_image(0, 0, image=self.photo, anchor='nw')
        except Exception as exc:
            self.delete('all')
            self.create_text(160, 80, text=f'Confira tema.json:\n{exc}', width=290, fill=colors['ink'])
