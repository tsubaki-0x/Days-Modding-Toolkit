"""Multi-game visual themes for the Days ModToolkit.

Themes are presentation-only. Archive detection remains in the GPK parser; the
GUI merely maps a successfully detected PIDX key name to a visual profile.
"""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

SKY = '#5FA8E8'
LIGHT = '#A9D7F5'
WHITE = '#F7F7F2'
NAVY = '#17283B'
INK = '#101820'
RED = '#C9363E'
ASSETS = Path(__file__).with_name('assets')

DEFAULT_THEME_ID = 'school_days'
SUMMER_THEME_ID = 'summer_days'
KEY_THEME_MAP = {
    'SCHOOL_DAYS_HQ': 'school_days',
    'SHINY_DAYS': 'shiny_days',
}

DEFAULT_PALETTE = {
    'sky': SKY,
    'light': LIGHT,
    'white': WHITE,
    'navy': NAVY,
    'ink': INK,
    'red': RED,
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def theme_path(theme_id: str) -> Path:
    return project_root() / 'themes' / theme_id / 'tema.json'


def theme_for_index_key(key_name: str | None) -> str | None:
    return KEY_THEME_MAP.get((key_name or '').upper())


def load_theme_profile(theme_id: str = DEFAULT_THEME_ID, *, allow_root_override: bool = True) -> dict:
    selected = theme_id if theme_path(theme_id).is_file() else DEFAULT_THEME_ID
    config = theme_path(selected)

    if selected == DEFAULT_THEME_ID and allow_root_override:
        root = project_root()
        candidates = [Path.cwd() / 'tema.json', root / 'tema.json']
        seen: set[Path] = set()
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.is_file():
                config = candidate
                break

    bundled = json.loads(theme_path(selected).read_text(encoding='utf-8'))
    data = dict(bundled)
    if config != theme_path(selected):
        override = json.loads(config.read_text(encoding='utf-8'))
        for key in ('imagem', 'opacidade', 'zoom', 'x', 'y'):
            if key in override:
                data[key] = override[key]

    data['id'] = selected
    data['_config_path'] = str(config)
    data['_theme_path'] = str(theme_path(selected))
    base = config.parent if config != theme_path(selected) else theme_path(selected).parent

    image = Path(data.get('imagem', 'Fundo.png'))
    if not image.is_absolute():
        image = base / image
    data['_image_path'] = str(image.resolve())

    logo_value = data.get('logo')
    if logo_value:
        logo = Path(logo_value)
        if not logo.is_absolute():
            logo = theme_path(selected).parent / logo
        data['_logo_path'] = str(logo.resolve())
    else:
        data['_logo_path'] = ''

    theme_palette = dict(DEFAULT_PALETTE)
    theme_palette.update(data.get('cores') or {})
    data['cores'] = theme_palette
    return data


def palette(profile: dict | None = None) -> dict:
    if profile is None:
        profile = load_theme_profile(DEFAULT_THEME_ID)
    result = dict(DEFAULT_PALETTE)
    result.update(profile.get('cores') or {})
    return result


def _shade(hex_color: str, factor: float) -> str:
    value = hex_color.lstrip('#')
    if len(value) != 6:
        return hex_color
    channels = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    if factor >= 1:
        channels = [round(c + (255 - c) * min(1, factor - 1)) for c in channels]
    else:
        channels = [round(c * max(0, factor)) for c in channels]
    return '#' + ''.join(f'{max(0, min(255, c)):02X}' for c in channels)


def apply_theme(root, profile: dict | str | None = None):
    if isinstance(profile, str):
        profile = load_theme_profile(profile, allow_root_override=(profile == DEFAULT_THEME_ID))
    elif profile is None:
        profile = load_theme_profile(DEFAULT_THEME_ID)
    colors = palette(profile)

    style = ttk.Style(root)
    style.theme_use('clam')
    root.configure(background=colors['navy'])
    root.option_add('*Font', ('Segoe UI', 10))
    style.configure('.', background=colors['navy'], foreground=colors['white'], font=('Segoe UI', 10))
    style.configure('TFrame', background=colors['navy'])
    style.configure('TLabel', background=colors['navy'], foreground=colors['white'])
    style.configure('TButton', padding=(12, 4), background=colors['light'], foreground=colors['ink'],
                    borderwidth=0, focusthickness=2, focuscolor=colors['sky'])
    style.map('TButton',
              background=[('disabled', _shade(colors['navy'], 1.45)),
                          ('pressed', _shade(colors['sky'], .86)),
                          ('active', colors['sky'])],
              foreground=[('disabled', _shade(colors['white'], .65))])
    style.configure('Primary.TButton', background=colors['red'], foreground=colors['white'],
                    font=('Segoe UI', 10, 'bold'))
    style.map('Primary.TButton',
              background=[('disabled', _shade(colors['navy'], 1.45)),
                          ('pressed', _shade(colors['red'], .72)),
                          ('active', _shade(colors['red'], .88))],
              foreground=[('disabled', _shade(colors['white'], .65)), ('!disabled', colors['white'])])
    style.configure('TEntry', fieldbackground=colors['navy'], foreground=colors['white'], padding=4,
                    bordercolor=colors['light'], lightcolor=colors['light'], darkcolor=colors['light'],
                    insertcolor=colors['white'], selectbackground=colors['sky'], selectforeground=colors['ink'])
    style.map('TEntry', bordercolor=[('focus', colors['sky'])],
              fieldbackground=[('disabled', colors['ink'])], foreground=[('disabled', colors['light'])])
    style.configure('TLabelframe', background=colors['navy'], bordercolor=colors['light'])
    style.configure('TLabelframe.Label', foreground=colors['white'], background=colors['navy'],
                    font=('Segoe UI', 10, 'bold'))
    style.configure('Treeview', background=colors['navy'], fieldbackground=colors['navy'],
                    foreground=colors['white'], rowheight=30, borderwidth=0)
    style.configure('Treeview.Heading', background=colors['navy'], foreground=colors['white'],
                    font=('Segoe UI', 10, 'bold'), padding=(8, 8), relief='flat')
    style.map('Treeview.Heading', background=[('active', _shade(colors['navy'], 1.22))])
    style.map('Treeview', background=[('selected', colors['sky'])], foreground=[('selected', colors['ink'])])
    style.configure('Horizontal.TProgressbar', background=colors['sky'], troughcolor=colors['light'],
                    borderwidth=0, thickness=7)
    return style


def _load_logo(parent, logo_path: str, max_width: int = 280, max_height: int = 76):
    path = Path(logo_path) if logo_path else None
    if not path or not path.is_file():
        return None
    try:
        from PIL import Image, ImageTk
        with Image.open(path) as original:
            image = original.convert('RGBA')
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image, master=parent)
    except ImportError:
        image = tk.PhotoImage(master=parent, file=str(path))
        factor = max(1, (image.width() + max_width - 1) // max_width,
                     (image.height() + max_height - 1) // max_height)
        return image.subsample(factor, factor) if factor > 1 else image


def update_header(header, version: str, profile: dict | str):
    if isinstance(profile, str):
        profile = load_theme_profile(profile, allow_root_override=(profile == DEFAULT_THEME_ID))
    colors = palette(profile)
    header.configure(background=colors['navy'])
    title_frame = header._theme_title_frame
    title_frame.configure(background=colors['navy'])

    logo = _load_logo(header, profile.get('_logo_path', ''))
    if logo is not None:
        header._theme_logo.configure(image=logo, text='', background=colors['navy'])
        header._theme_logo.image = logo
    else:
        header._theme_logo.configure(image='', text=profile.get('nome', 'Days'),
                                     foreground=colors['white'], background=colors['navy'],
                                     font=('Segoe UI', 22, 'bold'))
        header._theme_logo.image = None

    header._theme_title.configure(text=profile.get('cabecalho', 'MODDING TOOLKIT'),
                                  foreground=colors['white'], background=colors['navy'])
    subtitle = profile.get('subtitulo', '{version}').format(version=version)
    header._theme_subtitle.configure(text=subtitle, foreground=colors['light'], background=colors['navy'])
    return header


def add_header(parent, version, profile: dict | str | None = None):
    if profile is None:
        profile = load_theme_profile(DEFAULT_THEME_ID)
    elif isinstance(profile, str):
        profile = load_theme_profile(profile, allow_root_override=(profile == DEFAULT_THEME_ID))
    colors = palette(profile)

    header = tk.Frame(parent, background=colors['navy'], padx=20, pady=12)
    header.pack(fill='x', pady=(0, 12))
    logo_label = tk.Label(header, background=colors['navy'], borderwidth=0)
    logo_label.pack(side='left', anchor='n')
    title = tk.Frame(header, background=colors['navy'])
    title.pack(side='right', anchor='e')
    title_label = tk.Label(title, foreground=colors['white'], background=colors['navy'],
                           font=('Segoe UI', 13, 'bold'))
    title_label.pack(anchor='e')
    subtitle_label = tk.Label(title, foreground=colors['light'], background=colors['navy'],
                              font=('Segoe UI', 9))
    subtitle_label.pack(anchor='e', pady=(3, 0))

    header._theme_logo = logo_label
    header._theme_title_frame = title
    header._theme_title = title_label
    header._theme_subtitle = subtitle_label
    update_header(header, version, profile)
    return header
