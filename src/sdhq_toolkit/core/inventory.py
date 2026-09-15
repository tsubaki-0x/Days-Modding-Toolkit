from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .detection import detect_format
from .inspector import inspect_archive
from ..utils.binary import hex_bytes, read_prefix


def scan_packs(
    packs_dir: Path,
    include_hash: bool = True,
    progress: Callable[[int, int, Path], None] | None = None,
) -> dict:
    packs_dir = packs_dir.resolve()
    archives = []
    if packs_dir.exists():
        paths = sorted(packs_dir.rglob("*.gpk"), key=lambda item: str(item).lower())
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if progress is not None:
                progress(index, total, path)
            data = inspect_archive(path, include_hash=include_hash)
            data["relative_path"] = path.relative_to(packs_dir).as_posix()
            archives.append(data)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "packs_directory": str(packs_dir),
        "archive_count": len(archives),
        "total_size_bytes": sum(item["size_bytes"] for item in archives),
        "archives": archives,
    }


def scan_extracted(
    extracted_dir: Path,
    sample_header_bytes: int = 32,
    progress: Callable[[int, int, Path], None] | None = None,
) -> dict:
    extracted_dir = extracted_dir.resolve()
    files: list[dict] = []
    extension_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    headers_by_extension: dict[str, Counter[str]] = defaultdict(Counter)

    if extracted_dir.exists():
        candidates = [
            path
            for path in extracted_dir.rglob("*")
            if path.is_file()
            and path.name != ".gitkeep"
            and ".sdhq" not in path.relative_to(extracted_dir).parts
        ]
        candidates.sort(key=lambda item: str(item).lower())
        total = len(candidates)
        for index, path in enumerate(candidates, start=1):
            if progress is not None:
                progress(index, total, path)
            relative = path.relative_to(extracted_dir).as_posix()
            extension = path.suffix.lower() or "[no extension]"
            header = read_prefix(path, sample_header_bytes)
            size = path.stat().st_size
            detected = detect_format(header, extension, size)
            extension_counts[extension] += 1
            format_counts[detected] += 1
            headers_by_extension[extension][hex_bytes(header[:16])] += 1
            files.append(
                {
                    "path": relative,
                    "size_bytes": size,
                    "extension": extension,
                    "header_hex": hex_bytes(header),
                    "detected_format": detected,
                }
            )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extracted_directory": str(extracted_dir),
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "detected_format_counts": dict(sorted(format_counts.items())),
        "header_samples_by_extension": {
            ext: [{"header": header, "count": count} for header, count in counter.most_common(10)]
            for ext, counter in sorted(headers_by_extension.items())
        },
        "files": files,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.2f} {unit}"
        number /= 1024
    return f"{value} B"


def write_pack_reports(payload: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "gpk_inventory.json", payload)
    lines = [
        "SCHOOL DAYS HQ - GPK INVENTORY",
        f"Directory: {payload['packs_directory']}",
        f"Archives: {payload['archive_count']}",
        f"Total size: {_format_bytes(payload['total_size_bytes'])}",
        "",
    ]
    for index, archive in enumerate(payload["archives"], start=1):
        lines.extend(
            [
                f"[{index:03d}] {archive['relative_path']}",
                f"Size: {_format_bytes(archive['size_bytes'])} ({archive['size_bytes']} bytes)",
                f"SHA-256: {archive['sha256'] or '[skipped]'}",
                f"Header HEX: {archive['header_hex']}",
                f"Header ASCII: {archive['header_ascii']}",
                f"Footer HEX: {archive['footer_hex']}",
                f"Footer ASCII: {archive['footer_ascii']}",
                f"Detected format: {archive['stack_footer']['format']}",
                f"Index size: {archive['stack_footer']['index_size']}",
                f"Index offset: {archive['stack_footer']['index_offset']}",
                "",
            ]
        )
    (output_dir / "gpk_inventory.txt").write_text("\n".join(lines), encoding="utf-8")


def write_asset_reports(payload: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "asset_inventory.json", payload)
    lines = [
        "SCHOOL DAYS HQ - EXTRACTED ASSET INVENTORY",
        f"Directory: {payload['extracted_directory']}",
        f"Files: {payload['file_count']}",
        f"Total size: {_format_bytes(payload['total_size_bytes'])}",
        "",
        "EXTENSIONS",
    ]
    lines.extend(f"{ext}: {count}" for ext, count in payload["extension_counts"].items())
    lines.extend(["", "DETECTED FORMATS"])
    lines.extend(f"{name}: {count}" for name, count in payload["detected_format_counts"].items())
    lines.extend(["", "FILES"])
    for item in payload["files"]:
        lines.append(
            f"{item['path']} | {item['size_bytes']} bytes | {item['extension']} | "
            f"{item['detected_format']} | {item['header_hex']}"
        )
    (output_dir / "asset_inventory.txt").write_text("\n".join(lines), encoding="utf-8")

    unknown = [item for item in payload["files"] if item["detected_format"] == "UNKNOWN"]
    unknown_lines = [f"UNKNOWN FORMATS: {len(unknown)}", ""]
    unknown_lines.extend(
        f"{item['path']} | {item['extension']} | {item['size_bytes']} bytes | {item['header_hex']}"
        for item in unknown
    )
    (output_dir / "unknown_formats.txt").write_text("\n".join(unknown_lines), encoding="utf-8")
    write_asset_summary(summarize_asset_inventory(payload), output_dir)


def summarize_asset_inventory(payload: dict) -> dict:
    extension_counts: Counter[str] = Counter()
    extension_sizes: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    format_sizes: Counter[str] = Counter()
    archive_data: dict[str, dict] = {}
    unknown_files: list[dict] = []

    for item in payload.get("files", []):
        extension = item["extension"]
        size = item["size_bytes"]
        try:
            header = bytes.fromhex(item.get("header_hex", ""))
        except ValueError:
            header = b""
        detected = detect_format(header, extension, size)
        archive = item["path"].split("/", 1)[0]

        extension_counts[extension] += 1
        extension_sizes[extension] += size
        format_counts[detected] += 1
        format_sizes[detected] += size

        current = archive_data.setdefault(
            archive,
            {
                "file_count": 0,
                "total_size_bytes": 0,
                "extension_counts": Counter(),
                "extension_sizes": Counter(),
                "format_counts": Counter(),
                "format_sizes": Counter(),
            },
        )
        current["file_count"] += 1
        current["total_size_bytes"] += size
        current["extension_counts"][extension] += 1
        current["extension_sizes"][extension] += size
        current["format_counts"][detected] += 1
        current["format_sizes"][detected] += size
        if detected == "UNKNOWN":
            unknown_files.append(
                {
                    "path": item["path"],
                    "extension": extension,
                    "size_bytes": size,
                    "header_hex": item.get("header_hex", ""),
                }
            )

    def rows(counts: Counter[str], sizes: Counter[str], label: str) -> list[dict]:
        return [
            {label: name, "count": count, "size_bytes": sizes[name]}
            for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    archives = []
    for archive, data in sorted(archive_data.items(), key=lambda pair: pair[0].lower()):
        archives.append(
            {
                "archive": archive,
                "file_count": data["file_count"],
                "total_size_bytes": data["total_size_bytes"],
                "extensions": rows(data["extension_counts"], data["extension_sizes"], "extension"),
                "formats": rows(data["format_counts"], data["format_sizes"], "format"),
            }
        )

    return {
        "format": "SDHQ compact asset summary",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_inventory_generated_at_utc": payload.get("generated_at_utc"),
        "extracted_directory": payload.get("extracted_directory"),
        "file_count": sum(extension_counts.values()),
        "total_size_bytes": sum(extension_sizes.values()),
        "archive_count": len(archives),
        "extensions": rows(extension_counts, extension_sizes, "extension"),
        "detected_formats": rows(format_counts, format_sizes, "format"),
        "unknown_file_count": len(unknown_files),
        "unknown_files": unknown_files,
        "archives": archives,
    }


def write_asset_summary(summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "asset_summary.json", summary)
    lines = [
        "SCHOOL DAYS HQ - COMPACT ASSET SUMMARY",
        f"Archives: {summary['archive_count']}",
        f"Files: {summary['file_count']}",
        f"Total size: {_format_bytes(summary['total_size_bytes'])}",
        f"Unknown files: {summary['unknown_file_count']}",
        "",
        "FORMATS",
    ]
    lines.extend(
        f"{item['format']}: {item['count']} | {_format_bytes(item['size_bytes'])}"
        for item in summary["detected_formats"]
    )
    lines.extend(["", "ARCHIVES"])
    for archive in summary["archives"]:
        formats = ", ".join(f"{item['format']}={item['count']}" for item in archive["formats"])
        lines.append(
            f"{archive['archive']}: {archive['file_count']} files | "
            f"{_format_bytes(archive['total_size_bytes'])} | {formats}"
        )
    if summary["unknown_files"]:
        lines.extend(["", "UNKNOWN FILES"])
        lines.extend(
            f"{item['path']} | {item['size_bytes']} bytes | {item['header_hex']}"
            for item in summary["unknown_files"]
        )
    (output_dir / "asset_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def summarize_inventory_file(inventory_path: Path, output_dir: Path) -> dict:
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    summary = summarize_asset_inventory(payload)
    write_asset_summary(summary, output_dir)
    return summary


def run_inventory(
    packs_dir: Path,
    extracted_dir: Path | None,
    output_dir: Path,
    include_hash: bool = True,
    progress: Callable[[int, int, Path], None] | None = None,
) -> tuple[dict, dict | None]:
    packs = scan_packs(packs_dir, include_hash=include_hash, progress=progress)
    write_pack_reports(packs, output_dir)
    assets = None
    if extracted_dir is not None:
        assets = scan_extracted(extracted_dir)
        write_asset_reports(assets, output_dir)
    return packs, assets
