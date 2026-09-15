from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable

from .codec import (
    CMAP_PALETTE,
    decode_cmap,
    decode_colored_png,
    decode_png_rgba,
    encode_cmap,
    encode_colored_png,
    encode_overlay_png,
)


MANIFEST_NAME = "cmap_project.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"Unsafe path in CMAP manifest: {value}")
    return Path(*pure.parts)


def _resolve_inside(root: Path, relative: Path) -> Path:
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes its CMAP project root: {relative}") from exc
    return resolved


def _prepare_empty_directory(path: Path) -> Path:
    path = path.resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise FileExistsError(f"Output directory must be empty or absent: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def _companion_candidates(path: Path) -> list[Path]:
    suffixes = ("_WIDE_FULL", "_WIDE_NOTE", "_WIDE", "_FULL", "_NOTE", "_H")
    stems = [path.stem]
    upper = path.stem.upper()
    for suffix in suffixes:
        if upper.endswith(suffix):
            stems.append(path.stem[: -len(suffix)])
            break
    siblings = {
        item.name.lower(): item
        for item in path.parent.iterdir()
        if item.is_file() and item.suffix.lower() == ".png"
    }
    found = []
    for stem in stems:
        candidate = siblings.get(f"{stem}.png".lower())
        if candidate is not None and candidate not in found:
            found.append(candidate)
    return found


def _palette_legend_html(region_ids: list[int]) -> str:
    cards = "\n".join(
        (
            '<div class="item"><span class="swatch" '
            f'style="background:{"#%02X%02X%02X" % CMAP_PALETTE[value]}"></span>'
            f"<b>ID {value}</b><code>{'#%02X%02X%02X' % CMAP_PALETTE[value]}</code></div>"
        )
        for value in region_ids
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>SDHQ CMAP Palette</title>
<style>
body{{font:14px system-ui;background:#111;color:#eee;margin:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}}
.item{{display:grid;grid-template-columns:44px 1fr;grid-template-rows:1fr 1fr;
align-items:center;gap:0 10px;background:#222;padding:8px;border-radius:8px}}
.swatch{{grid-row:1/3;width:44px;height:44px;border:1px solid #777;border-radius:5px}}
code{{color:#bbb}}</style></head><body>
<h1>School Days HQ — IDs CMAP utilizados</h1>
<p>Cada cor corresponde exatamente a um byte/ID. Não suavize nem misture cores.</p>
<div class="grid">{cards}</div></body></html>"""


def export_cmap_project(
    source_directory: Path,
    output_directory: Path,
    progress: Callable[[int, int, Path], None] | None = None,
) -> dict:
    source_directory = source_directory.resolve()
    if not source_directory.is_dir():
        raise NotADirectoryError(f"CMAP source directory not found: {source_directory}")
    files = sorted(
        (
            path
            for path in source_directory.rglob("*")
            if path.is_file() and path.suffix.lower() == ".cmap"
        ),
        key=lambda path: str(path).lower(),
    )
    if not files:
        raise FileNotFoundError(f"No CMAP files found in: {source_directory}")
    output_directory = _prepare_empty_directory(output_directory)
    entries = []
    overlays_created = 0
    used_region_ids: set[int] = set()
    for index, path in enumerate(files, start=1):
        if progress is not None:
            progress(index, len(files), path)
        original = path.read_bytes()
        image = decode_cmap(original)
        relative = path.relative_to(source_directory)
        relative_text = relative.as_posix()
        editable_relative = Path("editable") / Path(relative_text + ".png")
        editable_data = encode_colored_png(image)
        _write_new(output_directory / editable_relative, editable_data)

        values = Counter(image.pixels)
        used_region_ids.update(values)
        entry = {
            "source_relative_path": relative_text,
            "source_sha256": _sha256(original),
            "width": image.width,
            "height": image.height,
            "region_ids": sorted(values),
            "region_pixel_counts": [
                {"id": value, "count": count} for value, count in sorted(values.items())
            ],
            "editable_relative_path": editable_relative.as_posix(),
            "editable_sha256": _sha256(editable_data),
            "overlay_relative_path": None,
            "companion_relative_path": None,
            "companion_resized": False,
            "overlay_error": None,
        }
        candidates = _companion_candidates(path)
        if candidates:
            companion = candidates[0]
            overlay_relative = Path("overlays") / Path(relative_text + ".png")
            try:
                companion_data = companion.read_bytes()
                companion_width, companion_height, _ = decode_png_rgba(companion_data)
                overlay_data = encode_overlay_png(image, companion_data)
                _write_new(output_directory / overlay_relative, overlay_data)
                entry["overlay_relative_path"] = overlay_relative.as_posix()
                entry["companion_relative_path"] = companion.relative_to(
                    source_directory
                ).as_posix()
                entry["companion_sha256"] = _sha256(companion_data)
                entry["companion_resized"] = (
                    companion_width != image.width or companion_height != image.height
                )
                overlays_created += 1
            except (OSError, ValueError) as exc:
                entry["overlay_error"] = str(exc)
        entries.append(entry)

    used_region_ids_list = sorted(used_region_ids)
    (output_directory / "palette_legend.html").write_text(
        _palette_legend_html(used_region_ids_list), encoding="utf-8"
    )
    # Record palette values explicitly so external tools do not need to reproduce the algorithm.
    manifest = {
        "format": "School Days HQ CMAP editing project",
        "manifest_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source_directory),
        "file_count": len(entries),
        "overlays_created": overlays_created,
        "used_region_ids": used_region_ids_list,
        "palette": [
            {"id": value, "rgb": list(color), "hex": "#%02X%02X%02X" % color}
            for value, color in enumerate(CMAP_PALETTE)
        ],
        "entries": entries,
    }
    (output_directory / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def build_cmap_project(
    project_directory: Path,
    output_directory: Path,
    source_directory: Path | None = None,
    allow_missing_marker: bool = False,
    allow_new_ids: bool = False,
    progress: Callable[[int, int, Path], None] | None = None,
) -> dict:
    project_directory = project_directory.resolve()
    manifest_path = project_directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"CMAP project manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 1 or not isinstance(manifest.get("entries"), list):
        raise ValueError("Unsupported or invalid CMAP project manifest")
    source_root = (source_directory or Path(manifest["source_directory"])).resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(f"CMAP source directory not found: {source_root}")
    output_directory = _prepare_empty_directory(output_directory)
    results = []
    modified = 0
    unchanged = 0
    failed = 0
    for index, entry in enumerate(manifest["entries"], start=1):
        relative_text = f"[manifest entry {index}]"
        try:
            relative_text = entry["source_relative_path"]
            if not isinstance(relative_text, str):
                raise TypeError("CMAP source path must be text")
            if progress is not None:
                progress(index, len(manifest["entries"]), Path(relative_text))
            relative = _safe_relative(relative_text)
            editable_relative = _safe_relative(entry["editable_relative_path"])
            source_path = _resolve_inside(source_root, relative)
            editable_path = _resolve_inside(project_directory, editable_relative)
            original = source_path.read_bytes()
            current_hash = _sha256(original)
            if current_hash != entry["source_sha256"]:
                raise ValueError("Source CMAP changed after project export")
            image = decode_colored_png(
                editable_path.read_bytes(), require_marker=not allow_missing_marker
            )
            if image.width != entry["width"] or image.height != entry["height"]:
                raise ValueError(
                    f"Edited image dimensions changed: expected {entry['width']}x{entry['height']}, "
                    f"got {image.width}x{image.height}"
                )
            new_ids = sorted(set(image.pixels) - set(entry["region_ids"]))
            if new_ids and not allow_new_ids:
                raise ValueError(
                    "Edited image introduces region IDs absent from the original CMAP: "
                    + ", ".join(map(str, new_ids))
                )
            rebuilt = encode_cmap(image)
            if rebuilt == original:
                status = "UNCHANGED"
                unchanged += 1
                output_path = None
            else:
                output_path = _resolve_inside(output_directory, relative)
                _write_new(output_path, rebuilt)
                status = "MODIFIED"
                modified += 1
            result = {
                "path": relative_text,
                "status": status,
                "original_sha256": current_hash,
                "rebuilt_sha256": _sha256(rebuilt),
                "output": str(output_path) if output_path is not None else None,
            }
        except (KeyError, OSError, TypeError, ValueError) as exc:
            result = {"path": relative_text, "status": "FAIL", "error": str(exc)}
            failed += 1
        results.append(result)
    report = {
        "format": "School Days HQ CMAP project build",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_directory": str(project_directory),
        "source_directory": str(source_root),
        "output_directory": str(output_directory),
        "file_count": len(results),
        "modified": modified,
        "unchanged": unchanged,
        "failed": failed,
        "status": "PASS" if failed == 0 else "FAIL",
        "files": results,
    }
    report_path = output_directory.parent / f"{output_directory.name}.build.json"
    report["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
