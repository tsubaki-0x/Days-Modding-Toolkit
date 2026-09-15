"""School Days palette; presentation only, independent of archive operations."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path

SKY = '#5FA8E8'
LIGHT = '#A9D7F5'
WHITE = '#F7F7F2'
NAVY = '#17283B'
INK = '#101820'
RED = '#C9363E'
ASSETS = Path(__file__).with_name('assets')


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')  # Native Windows themes ignore custom button colors.
    root.configure(background=NAVY)
    root.option_add('*Font', ('Segoe UI', 10))
    style.configure('.', background=NAVY, foreground=WHITE, font=('Segoe UI', 10))
    style.configure('TFrame', background=NAVY)
    style.configure('TLabel', background=NAVY, foreground=WHITE)
    style.configure('TButton', padding=(12, 4), background=LIGHT, foreground=NAVY,
                    borderwidth=0, focusthickness=2, focuscolor=NAVY)
    style.map('TButton', background=[('disabled', '#DFE5E8'), ('pressed', SKY), ('active', SKY)],
              foreground=[('disabled', '#657483')])
    style.configure('Primary.TButton', background=RED, foreground=WHITE, font=('Segoe UI', 10, 'bold'))
    style.map('Primary.TButton', background=[('disabled', '#DFE5E8'), ('pressed', '#962A30'), ('active', '#B32F36')],
              foreground=[('disabled', '#657483'), ('!disabled', WHITE)])
    style.configure('TEntry', fieldbackground=NAVY, foreground=WHITE, padding=4, bordercolor=LIGHT,
                    lightcolor=LIGHT, darkcolor=LIGHT, insertcolor=WHITE, selectbackground=SKY, selectforeground=INK)
    style.map('TEntry', bordercolor=[('focus', SKY)], fieldbackground=[('disabled', INK)], foreground=[('disabled', LIGHT)])
    style.configure('TLabelframe', background=NAVY, bordercolor=LIGHT)
    style.configure('TLabelframe.Label', foreground=WHITE, background=NAVY, font=('Segoe UI', 10, 'bold'))
    style.configure('Treeview', background=NAVY, fieldbackground=NAVY, foreground=WHITE,
                    rowheight=30, borderwidth=0)
    style.configure('Treeview.Heading', background=NAVY, foreground=WHITE,
                    font=('Segoe UI', 10, 'bold'), padding=(8, 8), relief='flat')
    style.map('Treeview.Heading', background=[('active', '#29435F')])
    style.map('Treeview', background=[('selected', SKY)], foreground=[('selected', INK)])
    style.configure('Horizontal.TProgressbar', background=SKY, troughcolor=LIGHT,
                    borderwidth=0, thickness=7)
    return style


def add_header(parent, version):
    header = tk.Frame(parent, background=NAVY, padx=20, pady=12)
    header.pack(fill='x', pady=(0, 12))
    try:
        logo = tk.PhotoImage(master=parent, file=str(ASSETS / 'school_days_logo.png'))
        label = tk.Label(header, image=logo, background=NAVY, borderwidth=0)
        label.image = logo
        label.pack(side='left', anchor='n')
    except tk.TclError:
        tk.Label(header, text='School Days', foreground=WHITE, background=NAVY,
                 font=('Segoe UI', 24, 'bold')).pack(side='left')
    title = tk.Frame(header, background=NAVY)
    title.pack(side='right', anchor='e')
    tk.Label(title, text='HQ  /  MODDING TOOLKIT', foreground=WHITE, background=NAVY,
             font=('Segoe UI', 13, 'bold')).pack(anchor='e')
    tk.Label(title, text=f'REPACK POR PASTA  ·  {version}', foreground=LIGHT, background=NAVY,
             font=('Segoe UI', 9)).pack(anchor='e', pady=(3, 0))
    return header
