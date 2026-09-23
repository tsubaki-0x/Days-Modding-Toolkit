"""Scrollable settings, leaving a separate area for results."""
import tkinter as tk
from tkinter import ttk
from .theme import NAVY

class ScrollForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, background=NAVY, highlightthickness=0, height=340)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = ttk.Frame(self.canvas, padding=12)
        window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(window, width=e.width))

    def set_background(self, color):
        """Update the canvas background when the active game theme changes."""
        self.canvas.configure(background=color)

    def enable_navigation(self):
        def wheel(event):
            if self.body.winfo_reqheight() > self.canvas.winfo_height():
                self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
                return 'break'
        def focus(event):
            self.update_idletasks()
            top = event.widget.winfo_rooty() - self.body.winfo_rooty()
            bottom = top + event.widget.winfo_height()
            visible = self.canvas.canvasy(0)
            height = self.canvas.winfo_height()
            total = max(1, self.body.winfo_height())
            if top < visible:
                self.canvas.yview_moveto(max(0, top - 8) / total)
            elif bottom > visible + height:
                self.canvas.yview_moveto(max(0, bottom - height + 8) / total)
        def bind_children(widget):
            widget.bind('<MouseWheel>', wheel, add='+')
            widget.bind('<FocusIn>', focus, add='+')
            for child in widget.winfo_children():
                bind_children(child)
        bind_children(self.body)
        self.canvas.bind('<MouseWheel>', wheel)
