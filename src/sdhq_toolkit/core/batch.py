from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from ..formats.gpk.index import read_stack_index
from ..formats.gpk.reader import GPKReader
from ..formats.gpk.writer import GPKWriter
from ..utils.hashing import workspace_stat_fingerprint


BatchProgress = Callable[[dict], None]
MIN_SPACE_MARGIN = 16 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_report(report: dict, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_name(report_path.name + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(report_path)


def _archives_in(directory: Path) -> list[Path]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"GPK directory not found: {directory}")
    archives = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".gpk"),
        key=lambda path: path.name.lower(),
    )
    if not archives:
        raise FileNotFoundError(f"No GPK archives found in: {directory}")
    stems: set[str] = set()
    for archive in archives:
        normalized = archive.stem.lower()
        if normalized in stems:
            raise ValueError(f"Duplicate archive stem (case-insensitive): {archive.stem}")
        stems.add(normalized)
    return archives


def _extraction_is_complete(archive: Path, destination: Path) -> bool:
    metadata_path = destination / ".sdhq" / "archive.json"
    if not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    source_name = Path(metadata.get("source_archive", "")).stem.lower()
    entries = metadata.get("entries")
    recorded_mtime = metadata.get("source_mtime_ns")
    return (
        metadata.get("format") == "GPK/STACK"
        and source_name == archive.stem.lower()
        and metadata.get("archive_size") == archive.stat().st_size
        and (recorded_mtime is None or recorded_mtime == archive.stat().st_mtime_ns)
        and isinstance(entries, list)
        and metadata.get("entry_count") == len(entries)
        and all(entry.get("extracted", True) for entry in entries)
    )


def _repack_is_complete(output: Path, reference: Path, source_directory: Path) -> bool:
    build_path = output.with_suffix(output.suffix + ".build.json")
    if not output.is_file() or not build_path.is_file():
        return False
    try:
        report = json.loads(build_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    try:
        metadata = json.loads(
            (source_directory / ".sdhq" / "archive.json").read_text(encoding="utf-8")
        )
        current_fingerprint = workspace_stat_fingerprint(
            source_directory,
            (entry["path"] for entry in metadata["entries"]),
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return False
    return (
        report.get("validation") == "PASS"
        and Path(report.get("reference", "")).stem.lower() == reference.stem.lower()
        and Path(report.get("source_directory", "")).name.lower() == source_directory.name.lower()
        and report.get("output_size") == output.stat().st_size
        and report.get("workspace_stat_fingerprint") == current_fingerprint
    )


def _space_status(target: Path, estimated_bytes: int, enabled: bool) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(target).free
    margin_bytes = max(MIN_SPACE_MARGIN, estimated_bytes // 100)
    required_bytes = estimated_bytes + margin_bytes
    return {
        "enabled": enabled,
        "estimated_bytes": estimated_bytes,
        "margin_bytes": margin_bytes,
        "required_bytes": required_bytes,
        "free_bytes": free_bytes,
        "passed": not enabled or free_bytes >= required_bytes,
    }


def _base_report(operation: str, source: Path, destination: Path) -> dict:
    return {
        "format": "SDHQ batch report",
        "operation": operation,
        "started_at": _utc_now(),
        "finished_at": None,
        "source": str(source.resolve()),
        "destination": str(destination.resolve()),
        "status": "RUNNING",
        "archives": [],
    }


def unpack_all(
    packs: Path,
    workspace: Path,
    key: bytes | None,
    report_path: Path,
    *,
    progress: BatchProgress | None = None,
    check_space: bool = True,
    stop_on_error: bool = False,
) -> dict:
    archives = _archives_in(packs)
    workspace = workspace.resolve()
    report = _base_report("unpack-all", packs, workspace)
    report["archive_count"] = len(archives)
    pending: list[tuple[Path, Path, dict]] = []
    estimated_bytes = 0

    for archive_index, archive in enumerate(archives, start=1):
        destination = workspace / archive.stem
        if _extraction_is_complete(archive, destination):
            result = {
                "archive": str(archive),
                "destination": str(destination),
                "status": "SKIPPED_COMPLETE",
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_skip", "index": archive_index, "total": len(archives), **result})
            continue
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not (destination / ".sdhq" / "archive.json").is_file():
            result = {
                "archive": str(archive),
                "destination": str(destination),
                "status": "FAILED",
                "error": "Destination exists but has no complete extraction marker",
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(archives), **result})
            if stop_on_error:
                break
            continue
        try:
            index_report = read_stack_index(archive, key)
            extracted_size = sum(
                entry["unpacked_size"] if entry["is_packed"] else entry["stored_size"]
                for entry in index_report["entries"]
            )
            estimated_bytes += extracted_size
            pending.append((archive, destination, index_report))
        except Exception as exc:
            result = {
                "archive": str(archive),
                "destination": str(destination),
                "status": "FAILED",
                "error": str(exc),
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(archives), **result})
            if stop_on_error:
                break

    report["space_check"] = _space_status(workspace, estimated_bytes, check_space)
    _write_report(report, report_path)
    if not report["space_check"]["passed"]:
        report["status"] = "INSUFFICIENT_SPACE"
        report["finished_at"] = _utc_now()
        _write_report(report, report_path)
        return report

    archive_positions = {archive.resolve(): index for index, archive in enumerate(archives, start=1)}
    for archive, destination, index_report in pending:
        archive_index = archive_positions[archive.resolve()]
        if progress is not None:
            progress(
                {
                    "event": "archive_start",
                    "index": archive_index,
                    "total": len(archives),
                    "archive": str(archive),
                    "entry_count": index_report["entry_count"],
                }
            )
        try:
            def entry_progress(index: int, total: int, path: str, size: int) -> None:
                if progress is not None:
                    progress(
                        {
                            "event": "entry",
                            "archive": str(archive),
                            "index": index,
                            "total": total,
                            "path": path,
                            "size": size,
                        }
                    )

            if (destination / ".sdhq" / "archive.json").is_file():
                from .partial import extract_selection
                metadata = extract_selection(archive, destination, key, progress=entry_progress)
            else:
                metadata = GPKReader(archive, key).extract(
                    destination,
                    progress=entry_progress,
                    index_report=index_report,
                )
            result = {
                "archive": str(archive),
                "destination": str(destination),
                "status": "PASS",
                "entry_count": metadata["entry_count"],
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_done", "index": archive_index, "total": len(archives), **result})
        except Exception as exc:
            result = {
                "archive": str(archive),
                "destination": str(destination),
                "status": "FAILED",
                "error": str(exc),
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(archives), **result})
            if stop_on_error:
                break
        _write_report(report, report_path)

    failures = sum(item["status"] == "FAILED" for item in report["archives"])
    passed = sum(item["status"] == "PASS" for item in report["archives"])
    skipped = sum(item["status"] == "SKIPPED_COMPLETE" for item in report["archives"])
    report.update(
        {
            "finished_at": _utc_now(),
            "status": "PASS" if failures == 0 else "PARTIAL",
            "passed_archives": passed,
            "skipped_archives": skipped,
            "failed_archives": failures,
        }
    )
    _write_report(report, report_path)
    return report


def repack_all(
    workspace: Path,
    references: Path,
    output: Path,
    key: bytes,
    report_path: Path,
    *,
    progress: BatchProgress | None = None,
    check_space: bool = True,
    stop_on_error: bool = False,
) -> dict:
    reference_archives = _archives_in(references)
    reference_by_stem = {archive.stem.lower(): archive for archive in reference_archives}
    workspace = workspace.resolve()
    output = output.resolve()
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace not found: {workspace}")
    source_directories = sorted(
        (
            path
            for path in workspace.iterdir()
            if path.is_dir() and (path / ".sdhq" / "archive.json").is_file()
        ),
        key=lambda path: path.name.lower(),
    )
    if not source_directories:
        raise FileNotFoundError(f"No completed GPK workspaces found in: {workspace}")

    report = _base_report("repack-all", workspace, output)
    report["reference_directory"] = str(references.resolve())
    report["archive_count"] = len(source_directories)
    pending: list[tuple[Path, Path, Path]] = []
    estimated_bytes = 0

    for archive_index, source_directory in enumerate(source_directories, start=1):
        reference = reference_by_stem.get(source_directory.name.lower())
        if reference is None:
            result = {
                "source_directory": str(source_directory),
                "status": "FAILED",
                "error": "Matching reference GPK not found",
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(source_directories), **result})
            if stop_on_error:
                break
            continue
        output_archive = output / f"{source_directory.name}.gpk"
        if _repack_is_complete(output_archive, reference, source_directory):
            result = {
                "reference": str(reference),
                "source_directory": str(source_directory),
                "output": str(output_archive),
                "status": "SKIPPED_COMPLETE",
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_skip", "index": archive_index, "total": len(source_directories), **result})
            continue
        if output_archive.exists():
            result = {
                "reference": str(reference),
                "source_directory": str(source_directory),
                "output": str(output_archive),
                "status": "FAILED",
                "error": "Output already exists without a matching PASS build report",
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(source_directories), **result})
            if stop_on_error:
                break
            continue
        pending.append((source_directory, reference, output_archive))
        estimated_bytes += reference.stat().st_size

    report["space_check"] = _space_status(output, estimated_bytes, check_space)
    _write_report(report, report_path)
    if not report["space_check"]["passed"]:
        report["status"] = "INSUFFICIENT_SPACE"
        report["finished_at"] = _utc_now()
        _write_report(report, report_path)
        return report

    source_positions = {path.resolve(): index for index, path in enumerate(source_directories, start=1)}
    for source_directory, reference, output_archive in pending:
        archive_index = source_positions[source_directory.resolve()]
        if progress is not None:
            progress(
                {
                    "event": "archive_start",
                    "index": archive_index,
                    "total": len(source_directories),
                    "archive": str(reference),
                }
            )
        try:
            def entry_progress(index: int, total: int, path: str, modified: bool) -> None:
                if progress is not None:
                    progress(
                        {
                            "event": "entry",
                            "archive": str(reference),
                            "index": index,
                            "total": total,
                            "path": path,
                            "modified": modified,
                        }
                    )

            build = GPKWriter(reference, key).repack(
                source_directory,
                output_archive,
                progress=entry_progress,
            )
            build_path = output_archive.with_suffix(output_archive.suffix + ".build.json")
            build_path.write_text(json.dumps(build, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {**build, "status": "PASS"}
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_done", "index": archive_index, "total": len(source_directories), **result})
        except Exception as exc:
            result = {
                "reference": str(reference),
                "source_directory": str(source_directory),
                "output": str(output_archive),
                "status": "FAILED",
                "error": str(exc),
            }
            report["archives"].append(result)
            if progress is not None:
                progress({"event": "archive_error", "index": archive_index, "total": len(source_directories), **result})
            if stop_on_error:
                break
        _write_report(report, report_path)

    failures = sum(item["status"] == "FAILED" for item in report["archives"])
    passed = sum(item["status"] == "PASS" for item in report["archives"])
    skipped = sum(item["status"] == "SKIPPED_COMPLETE" for item in report["archives"])
    report.update(
        {
            "finished_at": _utc_now(),
            "status": "PASS" if failures == 0 else "PARTIAL",
            "passed_archives": passed,
            "skipped_archives": skipped,
            "failed_archives": failures,
        }
    )
    _write_report(report, report_path)
    return report
