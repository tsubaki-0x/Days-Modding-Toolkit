from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..formats.assets.asf import compare_asf_compatibility, inspect_asf
from ..formats.assets.ogg import compare_ogg_compatibility, inspect_ogg
from ..formats.assets.png import compare_png_compatibility, inspect_png
from ..formats.cmap.codec import read_cmap
from ..utils.hashing import sha256_file
from ..utils.paths import safe_member_path


AssetProgress = Callable[[int, int, Path], None]
BASELINE_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(path: Path, payload: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _archive_metadata(workspace: Path) -> list[tuple[Path, dict]]:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace not found: {workspace}")
    archives = []
    for directory in sorted(workspace.iterdir(), key=lambda path: path.name.lower()):
        metadata_path = directory / ".sdhq" / "archive.json"
        if directory.is_dir() and metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("format") != "GPK/STACK" or not isinstance(metadata.get("entries"), list):
                raise ValueError(f"Invalid GPK extraction metadata: {metadata_path}")
            archives.append((directory, metadata))
    if not archives:
        raise FileNotFoundError(f"No completed GPK workspaces found in: {workspace}")
    return archives


def _format_name(path: Path) -> str:
    extension = path.suffix.lower()
    return {
        ".png": "PNG",
        ".ogg": "Ogg",
        ".wmv": "ASF/WMV",
        ".asf": "ASF/WMV",
        ".cmap": "CMAP",
        ".ors": "ORS",
        ".ini": "INI",
        ".txt": "TXT",
        ".dat": "DAT/UNKNOWN",
    }.get(extension, "UNKNOWN")


def _inspect_asset(path: Path, format_name: str, *, full_validation: bool) -> dict:
    if format_name == "PNG":
        return inspect_png(path, full_validation=full_validation)
    if format_name == "Ogg":
        return inspect_ogg(path, full_validation=full_validation)
    if format_name == "ASF/WMV":
        return inspect_asf(path, full_validation=full_validation)
    if format_name == "CMAP":
        image = read_cmap(path)
        return {
            "format": "CMAP",
            "size_bytes": path.stat().st_size,
            "width": image.width,
            "height": image.height,
            "region_ids": sorted(set(image.pixels)),
            "full_validation": True,
        }
    if format_name in ("ORS", "INI", "TXT"):
        data = path.read_bytes()
        encoding = "utf-8"
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        elif data.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        else:
            try:
                data.decode(encoding)
            except UnicodeError:
                encoding = "cp932"
        decoded = data.decode(encoding)
        if "\x00" in decoded:
            raise ValueError("NUL in text asset")
        import re
        sections = re.findall(r"^\s*\[([^\]\r\n]+)\]", decoded, re.MULTILINE)
        keys = re.findall(r"^\s*([^;#\s=\[\]][^=\r\n]*?)\s*=", decoded, re.MULTILINE)
        return {
            "format": format_name,
            "size_bytes": len(data),
            "encoding": encoding.upper(),
            "sections": sections,
            "keys": keys,
            "line_count": len(decoded.splitlines()),
            "newlines": "CRLF" if b"\r\n" in data else "LF",
            "full_validation": True,
        }
    with path.open("rb") as stream:
        signature = stream.read(32).hex(" ")
    return {"format": format_name, "signature": signature, "size_bytes": path.stat().st_size,
            "warning": "Formato desconhecido: compatibilidade não verificada", "full_validation": False}


def create_asset_baseline(
    workspace: Path,
    output: Path,
    *,
    progress: AssetProgress | None = None,
) -> dict:
    workspace = workspace.resolve()
    archives = _archive_metadata(workspace)
    total = sum(len(metadata["entries"]) for _, metadata in archives)
    results = []
    failed = 0
    index = 0
    for archive_directory, metadata in archives:
        for entry in metadata["entries"]:
            if not entry.get("extracted", True):
                continue
            index += 1
            relative_path = entry["path"]
            asset_path = safe_member_path(archive_directory, relative_path)
            if progress is not None:
                progress(index, total, asset_path)
            format_name = _format_name(asset_path)
            try:
                if not asset_path.is_file():
                    raise FileNotFoundError(f"Missing extracted asset: {asset_path}")
                current_hash = sha256_file(asset_path)
                expected_hash = entry.get("extracted_sha256")
                if not expected_hash or current_hash != expected_hash:
                    raise ValueError("Workspace is not clean relative to extraction metadata")
                properties = _inspect_asset(asset_path, format_name, full_validation=False)
                result = {
                    "archive": archive_directory.name,
                    "path": relative_path,
                    "format": format_name,
                    "size_bytes": asset_path.stat().st_size,
                    "sha256": current_hash,
                    "properties": properties,
                    "status": "PASS",
                }
            except (OSError, UnicodeError, ValueError) as exc:
                failed += 1
                result = {
                    "archive": archive_directory.name,
                    "path": relative_path,
                    "format": format_name,
                    "status": "FAIL",
                    "error": str(exc),
                }
            results.append(result)
    format_counts = Counter(item["format"] for item in results)
    baseline = {
        "format": "School Days HQ asset compatibility baseline",
        "baseline_version": BASELINE_VERSION,
        "generated_at": _utc_now(),
        "workspace": str(workspace),
        "archive_count": len(archives),
        "file_count": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "status": "PASS" if failed == 0 else "FAIL",
        "format_counts": dict(sorted(format_counts.items())),
        "entries": results,
    }
    _write_json_atomic(output, baseline)
    return baseline


def _compare_properties(format_name: str, original: dict, modified: dict) -> tuple[list[str], list[str]]:
    if format_name == "PNG":
        return compare_png_compatibility(original, modified)
    if format_name == "Ogg":
        return compare_ogg_compatibility(original, modified)
    if format_name == "ASF/WMV":
        return compare_asf_compatibility(original, modified)
    errors: list[str] = []
    warnings: list[str] = []
    if format_name == "CMAP":
        if (modified["width"], modified["height"]) != (original["width"], original["height"]):
            errors.append(
                f"dimensions changed from {original['width']}x{original['height']} to "
                f"{modified['width']}x{modified['height']}"
            )
        new_ids = sorted(set(modified["region_ids"]) - set(original["region_ids"]))
        if new_ids:
            errors.append("new CMAP region IDs: " + ", ".join(map(str, new_ids)))
    if format_name in ("ORS", "INI", "TXT"):
        legacy_utf8_bom = ("sections" not in original and original.get("encoding") == "UTF-8"
                           and modified.get("encoding") == "UTF-8-SIG")
        if original.get("encoding") != modified.get("encoding") and not legacy_utf8_bom:
            errors.append("text encoding changed")
        for field in ("sections", "keys"):
            if field in original and original[field] != modified.get(field):
                errors.append(f"text structure changed: {field}")
        if "newlines" in original and original["newlines"] != modified.get("newlines"):
            warnings.append("text newline convention changed")
    return errors, warnings


def validate_modified_assets(
    workspace: Path,
    baseline_path: Path,
    output: Path | None,
    *,
    allow_unknown: bool = False,
    progress: AssetProgress | None = None,
) -> dict:
    workspace = workspace.resolve()
    single_archive = (workspace / ".sdhq" / "archive.json").is_file()
    workspace_root = workspace.parent if single_archive else workspace
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("baseline_version") != BASELINE_VERSION or baseline.get("status") != "PASS":
        raise ValueError("Asset baseline is invalid, unsupported or incomplete")
    entries = baseline.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Asset baseline has no entry list")
    if single_archive:
        entries = [entry for entry in entries if entry.get("archive", "").lower() == workspace.name.lower()]
        if not entries:
            raise ValueError(f"Asset baseline has no entries for archive: {workspace.name}")
    expected_paths: set[Path] = set()
    results = []
    modified_count = 0
    unchanged_count = 0
    failed_count = 0
    warning_count = 0
    for index, entry in enumerate(entries, start=1):
        archive_directory = workspace_root / entry["archive"]
        asset_path = safe_member_path(archive_directory, entry["path"])
        expected_paths.add(asset_path.resolve())
        if progress is not None:
            progress(index, len(entries), asset_path)
        try:
            if not asset_path.is_file():
                raise FileNotFoundError("Asset is missing from workspace")
            current_hash = sha256_file(asset_path)
            if current_hash == entry["sha256"]:
                unchanged_count += 1
                continue
            modified_count += 1
            format_name = entry["format"]
            if format_name in ("UNKNOWN", "DAT/UNKNOWN") and not allow_unknown:
                raise ValueError("Modified unknown format requires --allow-unknown")
            modified_properties = _inspect_asset(asset_path, format_name, full_validation=True)
            errors, warnings = _compare_properties(
                format_name, entry["properties"], modified_properties
            )
            if errors:
                raise ValueError("; ".join(errors))
            warning_count += len(warnings)
            results.append(
                {
                    "archive": entry["archive"],
                    "path": entry["path"],
                    "format": format_name,
                    "status": "PASS",
                    "original_sha256": entry["sha256"],
                    "modified_sha256": current_hash,
                    "original_properties": entry["properties"],
                    "modified_properties": modified_properties,
                    "warnings": warnings,
                }
            )
        except (KeyError, OSError, UnicodeError, ValueError) as exc:
            failed_count += 1
            results.append(
                {
                    "archive": entry.get("archive"),
                    "path": entry.get("path"),
                    "format": entry.get("format"),
                    "status": "FAIL",
                    "error": str(exc),
                }
            )

    extra_files = []
    scan_root = workspace if single_archive else workspace_root
    for path in scan_root.rglob("*"):
        if not path.is_file() or ".sdhq" in path.relative_to(scan_root).parts:
            continue
        if path.resolve() not in expected_paths:
            extra_files.append(path.relative_to(scan_root).as_posix())
    if extra_files:
        failed_count += len(extra_files)
        results.extend(
            {"path": path, "format": "EXTRA", "status": "FAIL", "error": "Extra entries are unsupported"}
            for path in sorted(extra_files)
        )
    report = {
        "format": "School Days HQ modified asset validation",
        "generated_at": _utc_now(),
        "workspace": str(workspace),
        "baseline": str(baseline_path.resolve()),
        "file_count": len(entries),
        "modified": modified_count,
        "unchanged": unchanged_count,
        "extra": len(extra_files),
        "failed": failed_count,
        "warnings": warning_count,
        "status": "PASS" if failed_count == 0 else "FAIL",
        "modified_files": results,
    }
    if output is not None:
        _write_json_atomic(output, report)
    return report
