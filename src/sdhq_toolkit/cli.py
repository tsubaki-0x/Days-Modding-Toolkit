from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from .core.batch import repack_all, unpack_all
from .core.asset_validation import create_asset_baseline, validate_modified_assets
from .core.comparison import compare_files
from .core.extractor import unpack_archive
from .core.inspector import inspect_archive
from .core.inventory import (
    run_inventory,
    scan_extracted,
    summarize_inventory_file,
    write_asset_reports,
)
from .core.key_extractor import find_ciphercode, save_key_report
from .core.mods import (
    apply_mod_package,
    build_mod_package,
    create_mod_project,
    inspect_mod_package,
    remove_mod_from_workspace,
    save_mod_report,
)
from .core.repacker import repack_archive
from .core.validator import validate_basic_archive
from .errors import ToolkitError
from .formats.gpk.index import load_key_report, read_stack_index, save_index_report
from .formats.cmap.codec import (
    cmap_overlay,
    cmap_to_colored_png,
    cmap_to_png,
    colored_png_to_cmap,
    png_to_cmap,
    verify_cmap_directory,
)
from .formats.cmap.project import build_cmap_project, export_cmap_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdhq", description="School Days HQ / Shiny Days Modding Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Scan GPK archives and extracted files")
    inventory.add_argument("--packs", type=Path, required=True)
    inventory.add_argument("--extracted", type=Path)
    inventory.add_argument("--output", type=Path, default=Path("reports"))
    inventory.add_argument(
        "--skip-hash",
        action="store_true",
        help="Skip SHA-256 for a fast footer/header rescan",
    )

    inspect = subparsers.add_parser("inspect", help="Inspect a raw archive safely")
    inspect.add_argument("archive", type=Path)

    scan_assets = subparsers.add_parser("scan-assets", help="Scan already extracted files")
    scan_assets.add_argument("directory", type=Path)
    scan_assets.add_argument("--output", type=Path, default=Path("reports"))
    scan_assets.add_argument("--progress-every", type=int, default=1000)

    summarize_assets = subparsers.add_parser(
        "summarize-assets",
        help="Create a compact reclassified summary from asset_inventory.json",
    )
    summarize_assets.add_argument("inventory", type=Path)
    summarize_assets.add_argument("--output", type=Path, default=Path("reports"))

    asset_baseline = subparsers.add_parser(
        "asset-baseline",
        help="Create a clean compatibility baseline for every extracted asset",
    )
    asset_baseline.add_argument("workspace", type=Path)
    asset_baseline.add_argument(
        "--output",
        type=Path,
        default=Path("reports/asset_baseline.json"),
    )
    asset_baseline.add_argument("--progress-every", type=int, default=500)

    asset_validate = subparsers.add_parser(
        "asset-validate",
        help="Validate modified assets against a clean compatibility baseline",
    )
    asset_validate.add_argument("workspace", type=Path)
    asset_validate.add_argument("--baseline", type=Path, required=True)
    asset_validate.add_argument(
        "--output",
        type=Path,
        default=Path("reports/asset_validation.json"),
    )
    asset_validate.add_argument("--allow-unknown", action="store_true")
    asset_validate.add_argument("--progress-every", type=int, default=500)

    cmap_export = subparsers.add_parser("cmap-to-png", help="Export one CMAP as lossless PNG")
    cmap_export.add_argument("source", type=Path)
    cmap_export.add_argument("--output", type=Path, required=True)

    cmap_import = subparsers.add_parser("png-to-cmap", help="Import one 8-bit PNG as CMAP")
    cmap_import.add_argument("source", type=Path)
    cmap_import.add_argument("--output", type=Path, required=True)

    cmap_color_export = subparsers.add_parser(
        "cmap-to-color",
        help="Export one CMAP with a lossless visible region palette",
    )
    cmap_color_export.add_argument("source", type=Path)
    cmap_color_export.add_argument("--output", type=Path, required=True)

    cmap_color_import = subparsers.add_parser(
        "color-to-cmap",
        help="Import one protected CMAP palette PNG",
    )
    cmap_color_import.add_argument("source", type=Path)
    cmap_color_import.add_argument("--output", type=Path, required=True)
    cmap_color_import.add_argument("--allow-missing-marker", action="store_true")

    cmap_overlay_parser = subparsers.add_parser(
        "cmap-overlay",
        help="Overlay colored CMAP regions on a companion PNG",
    )
    cmap_overlay_parser.add_argument("source", type=Path)
    cmap_overlay_parser.add_argument("--image", type=Path, required=True)
    cmap_overlay_parser.add_argument("--output", type=Path, required=True)
    cmap_overlay_parser.add_argument("--opacity", type=float, default=0.58)

    cmap_project_export = subparsers.add_parser(
        "cmap-project-export",
        help="Export every CMAP into a protected visual editing project",
    )
    cmap_project_export.add_argument("directory", type=Path)
    cmap_project_export.add_argument("--output", type=Path, required=True)
    cmap_project_export.add_argument("--progress-every", type=int, default=1)

    cmap_project_build = subparsers.add_parser(
        "cmap-project-build",
        help="Build only modified CMAP files into a staging directory",
    )
    cmap_project_build.add_argument("project", type=Path)
    cmap_project_build.add_argument("--output", type=Path, required=True)
    cmap_project_build.add_argument("--source", type=Path)
    cmap_project_build.add_argument("--allow-missing-marker", action="store_true")
    cmap_project_build.add_argument("--allow-new-ids", action="store_true")
    cmap_project_build.add_argument("--progress-every", type=int, default=1)

    cmap_verify = subparsers.add_parser(
        "verify-cmap",
        help="Validate CMAP to PNG to CMAP round-trip recursively",
    )
    cmap_verify.add_argument("directory", type=Path)
    cmap_verify.add_argument(
        "--output",
        type=Path,
        default=Path("reports/cmap_roundtrip.json"),
    )

    compare = subparsers.add_parser("compare", help="Compare two binary archives")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)

    verify = subparsers.add_parser("verify", help="Run non-destructive basic checks")
    verify.add_argument("archive", type=Path)

    unpack = subparsers.add_parser("unpack", help="Extract or resume a GPK, optionally selecting indexed members")
    unpack.add_argument("archive", type=Path)
    unpack.add_argument("--workspace", type=Path, default=Path("workspace"))
    unpack.add_argument("--key-report", type=Path, help="Optional CIPHERCODE/PIDX key report; known game keys are auto-detected when omitted")
    unpack.add_argument("--member", action="append", help="Extract only this indexed path; repeat for multiple files")

    unpack_all_parser = subparsers.add_parser(
        "unpack-all",
        help="Extract every GPK in a directory with archive-level resume",
    )
    unpack_all_parser.add_argument("packs", type=Path)
    unpack_all_parser.add_argument("--workspace", type=Path, default=Path("workspace"))
    unpack_all_parser.add_argument("--key-report", type=Path, help="Optional CIPHERCODE/PIDX key report; known game keys are auto-detected when omitted")
    unpack_all_parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/unpack_all_report.json"),
    )
    unpack_all_parser.add_argument("--progress-every", type=int, default=100)
    unpack_all_parser.add_argument("--no-space-check", action="store_true")
    unpack_all_parser.add_argument("--stop-on-error", action="store_true")

    repack = subparsers.add_parser("repack", help="Repack a folder using an original reference")
    repack.add_argument("directory", type=Path)
    repack.add_argument("--reference", type=Path, required=True)
    repack.add_argument("--output", type=Path, default=Path("output"))
    repack.add_argument("--key-report", type=Path, help="Optional CIPHERCODE/PIDX key report; known game keys are auto-detected when omitted")
    repack.add_argument("--asset-baseline", type=Path)
    repack.add_argument("--asset-progress-every", type=int, default=500)

    repack_all_parser = subparsers.add_parser(
        "repack-all",
        help="Repack every completed GPK workspace using original references",
    )
    repack_all_parser.add_argument("workspace", type=Path)
    repack_all_parser.add_argument("--references", type=Path, required=True)
    repack_all_parser.add_argument("--output", type=Path, default=Path("output"))
    repack_all_parser.add_argument("--key-report", type=Path, help="Optional CIPHERCODE/PIDX key report; known game keys are auto-detected when omitted")
    repack_all_parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/repack_all_report.json"),
    )
    repack_all_parser.add_argument("--progress-every", type=int, default=100)
    repack_all_parser.add_argument("--no-space-check", action="store_true")
    repack_all_parser.add_argument("--stop-on-error", action="store_true")
    repack_all_parser.add_argument("--asset-baseline", type=Path)

    key = subparsers.add_parser("extract-key", help="Read the Stack CIPHERCODE resource safely")
    key.add_argument("game_directory", type=Path)
    key.add_argument("--output", type=Path, default=Path("reports/ciphercode_report.json"))

    index = subparsers.add_parser("read-index", help="Decrypt and parse a GPK/STACK index")
    index.add_argument("archive", type=Path)
    index.add_argument("--key-report", type=Path, help="Optional CIPHERCODE/PIDX key report; known game keys are auto-detected when omitted")
    index.add_argument("--output", type=Path)

    mod_create = subparsers.add_parser("mod-create", help="Create a distributable mod project")
    mod_create.add_argument("directory", type=Path)
    mod_create.add_argument("--id", required=True)
    mod_create.add_argument("--name", required=True)
    mod_create.add_argument("--author", required=True)
    mod_create.add_argument("--version", default="1.0.0")
    mod_create.add_argument("--description", default="")
    mod_create.add_argument("--archives", nargs="*", default=[])

    mod_build = subparsers.add_parser(
        "mod-build",
        help="Build a .sdmod with only modified workspace files",
    )
    mod_build.add_argument("project", type=Path)
    mod_build.add_argument("--workspace", type=Path, required=True)
    mod_build.add_argument("--output", type=Path, default=Path("dist"))
    mod_build.add_argument("--asset-baseline", type=Path)
    mod_build.add_argument("--allow-unknown", action="store_true")
    mod_build.add_argument("--progress-every", type=int, default=500)

    mod_inspect = subparsers.add_parser(
        "mod-inspect",
        help="Verify and describe a .sdmod package",
    )
    mod_inspect.add_argument("package", type=Path)
    mod_inspect.add_argument("--report", type=Path)
    mod_inspect.add_argument("--progress-every", type=int, default=100)

    mod_apply = subparsers.add_parser(
        "mod-apply",
        help="Apply a verified .sdmod to a clean extracted workspace",
    )
    mod_apply.add_argument("package", type=Path)
    mod_apply.add_argument("--workspace", type=Path, required=True)
    mod_apply.add_argument("--report", type=Path, default=Path("reports/mod_apply.json"))
    mod_apply.add_argument("--progress-every", type=int, default=100)

    mod_remove = subparsers.add_parser(
        "mod-remove",
        help="Restore workspace files changed by an applied mod",
    )
    mod_remove.add_argument("mod_id")
    mod_remove.add_argument("--workspace", type=Path, required=True)
    mod_remove.add_argument("--report", type=Path, default=Path("reports/mod_remove.json"))
    mod_remove.add_argument("--progress-every", type=int, default=100)
    return parser


def _show_batch_progress(event: dict, every: int) -> None:
    event_type = event["event"]
    if event_type == "archive_start":
        print(
            f"\n[{event['index']:02d}/{event['total']:02d}] {Path(event['archive']).name}",
            flush=True,
        )
    elif event_type == "entry":
        index = event["index"]
        total = event["total"]
        modified = event.get("modified", False)
        if index == 1 or index == total or index % every == 0 or modified:
            suffix = " [MODIFIED]" if modified else ""
            print(f"  [{index}/{total}] {event['path']}{suffix}", flush=True)
    elif event_type == "archive_skip":
        path = event.get("archive") or event.get("reference") or event.get("source_directory")
        print(
            f"[{event['index']:02d}/{event['total']:02d}] {Path(path).name}: already complete, skipped",
            flush=True,
        )
    elif event_type == "archive_done":
        print(f"  [PASS] {Path(event.get('archive', event.get('output', 'archive'))).name}", flush=True)
    elif event_type == "archive_error":
        path = event.get("archive") or event.get("reference") or event.get("source_directory")
        print(f"  [FAIL] {Path(path).name}: {event['error']}", flush=True)


def _show_mod_progress(index: int, total: int, path: str, every: int) -> None:
    if index == 1 or index == total or index % every == 0:
        print(f"[{index}/{total}] {path}", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inventory":
            def show_progress(index: int, total: int, path: Path) -> None:
                mode = "hash + signatures" if not args.skip_hash else "signatures"
                print(f"[{index:02d}/{total:02d}] {path.name} ({mode})", flush=True)

            packs, assets = run_inventory(
                args.packs,
                args.extracted,
                args.output,
                include_hash=not args.skip_hash,
                progress=show_progress,
            )
            print(f"[OK] {packs['archive_count']} GPK(s) catalogado(s).")
            if assets is not None:
                print(f"[OK] {assets['file_count']} arquivo(s) extraído(s) analisado(s).")
            print(f"[OK] Relatórios: {args.output.resolve()}")
        elif args.command == "inspect":
            print(json.dumps(inspect_archive(args.archive), ensure_ascii=False, indent=2))
        elif args.command == "scan-assets":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")

            def show_asset_progress(index: int, total: int, path: Path) -> None:
                if index == 1 or index == total or index % args.progress_every == 0:
                    print(f"[{index}/{total}] {path.name}", flush=True)

            payload = scan_extracted(args.directory, progress=show_asset_progress)
            write_asset_reports(payload, args.output)
            print(f"[OK] {payload['file_count']} arquivo(s) analisado(s).")
            print(f"[OK] Resumo: {(args.output / 'asset_summary.json').resolve()}")
        elif args.command == "summarize-assets":
            summary = summarize_inventory_file(args.inventory, args.output)
            print(f"[PASS] {summary['file_count']} files summarized.")
            print(f"[OK] Unknown files: {summary['unknown_file_count']}")
            print(f"[OK] Output: {(args.output / 'asset_summary.json').resolve()}")
        elif args.command == "asset-baseline":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")

            def show_baseline_progress(index: int, total: int, path: Path) -> None:
                if index == 1 or index == total or index % args.progress_every == 0:
                    print(f"[{index}/{total}] {path.name}", flush=True)

            report = create_asset_baseline(
                args.workspace,
                args.output,
                asset_baseline=args.asset_baseline,
                allow_unknown=args.allow_unknown,
                progress=show_baseline_progress,
            )
            print(
                f"[{report['status']}] Asset baseline: {report['passed']} passed, "
                f"{report['failed']} failed."
            )
            print(f"[OK] Output: {args.output.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "asset-validate":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")

            def show_validation_progress(index: int, total: int, path: Path) -> None:
                if index == 1 or index == total or index % args.progress_every == 0:
                    print(f"[{index}/{total}] {path.name}", flush=True)

            report = validate_modified_assets(
                args.workspace,
                args.baseline,
                args.output,
                allow_unknown=args.allow_unknown,
                progress=show_validation_progress,
            )
            print(
                f"[{report['status']}] Assets: {report['modified']} modified, "
                f"{report['unchanged']} unchanged, {report['failed']} failed, "
                f"{report['warnings']} warning(s)."
            )
            print(f"[OK] Output: {args.output.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "cmap-to-png":
            image = cmap_to_png(args.source, args.output)
            print(f"[PASS] CMAP exported: {image.width}x{image.height}")
            print(f"[OK] Output: {args.output.resolve()}")
        elif args.command == "png-to-cmap":
            image = png_to_cmap(args.source, args.output)
            print(f"[PASS] CMAP rebuilt: {image.width}x{image.height}")
            print(f"[OK] Output: {args.output.resolve()}")
        elif args.command == "cmap-to-color":
            image = cmap_to_colored_png(args.source, args.output)
            print(f"[PASS] Colored CMAP exported: {image.width}x{image.height}")
            print(f"[OK] Output: {args.output.resolve()}")
        elif args.command == "color-to-cmap":
            image = colored_png_to_cmap(
                args.source,
                args.output,
                require_marker=not args.allow_missing_marker,
            )
            print(f"[PASS] Colored CMAP rebuilt: {image.width}x{image.height}")
            print(f"[OK] Output: {args.output.resolve()}")
        elif args.command == "cmap-overlay":
            image = cmap_overlay(args.source, args.image, args.output, opacity=args.opacity)
            print(f"[PASS] CMAP overlay created: {image.width}x{image.height}")
            print(f"[OK] Output: {args.output.resolve()}")
        elif args.command == "cmap-project-export":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")

            def show_cmap_export(index: int, total: int, path: Path) -> None:
                if index == 1 or index == total or index % args.progress_every == 0:
                    print(f"[{index}/{total}] {path.name}", flush=True)

            report = export_cmap_project(args.directory, args.output, progress=show_cmap_export)
            print(f"[PASS] {report['file_count']} colored CMAP files exported.")
            print(f"[OK] Overlays created: {report['overlays_created']}")
            print(f"[OK] Project: {args.output.resolve()}")
        elif args.command == "cmap-project-build":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")

            def show_cmap_build(index: int, total: int, path: Path) -> None:
                if index == 1 or index == total or index % args.progress_every == 0:
                    print(f"[{index}/{total}] {path}", flush=True)

            report = build_cmap_project(
                args.project,
                args.output,
                source_directory=args.source,
                allow_missing_marker=args.allow_missing_marker,
                allow_new_ids=args.allow_new_ids,
                progress=show_cmap_build,
            )
            print(
                f"[{report['status']}] CMAP build: {report['modified']} modified, "
                f"{report['unchanged']} unchanged, {report['failed']} failed."
            )
            print(f"[OK] Staging: {args.output.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "verify-cmap":
            report = verify_cmap_directory(args.directory, args.output)
            print(
                f"[{report['status']}] CMAP round-trip: "
                f"{report['passed']} passed, {report['failed']} failed."
            )
            print(f"[OK] Report: {args.output.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "compare":
            print(json.dumps(compare_files(args.left, args.right), ensure_ascii=False, indent=2))
        elif args.command == "verify":
            errors = validate_basic_archive(args.archive)
            if errors:
                print("[FAIL] " + "; ".join(errors), file=sys.stderr)
                return 1
            print("[PASS] Verificações básicas concluídas.")
        elif args.command == "unpack":
            key_bytes = load_key_report(args.key_report) if args.key_report else None
            destination, metadata = unpack_archive(args.archive, args.workspace, key_bytes, paths=args.member)
            extracted = sum(entry.get("extracted", True) for entry in metadata["entries"])
            print(f"[PASS] {extracted}/{metadata['entry_count']} entries extracted from {args.archive.name}.")
            print(f"[OK] Destination: {destination.resolve()}")
        elif args.command == "unpack-all":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            key_bytes = load_key_report(args.key_report) if args.key_report else None
            report = unpack_all(
                args.packs,
                args.workspace,
                key_bytes,
                args.report,
                progress=lambda event: _show_batch_progress(event, args.progress_every),
                check_space=not args.no_space_check,
                stop_on_error=args.stop_on_error,
            )
            space = report["space_check"]
            print(
                f"\n[SPACE] required={space['required_bytes']} free={space['free_bytes']} "
                f"status={'PASS' if space['passed'] else 'FAIL'}"
            )
            print(
                f"[{report['status']}] extracted={report.get('passed_archives', 0)} "
                f"skipped={report.get('skipped_archives', 0)} "
                f"failed={report.get('failed_archives', 0)}"
            )
            print(f"[OK] Report: {args.report.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "repack":
            if args.asset_baseline is not None:
                if args.asset_progress_every < 1:
                    raise ValueError("--asset-progress-every must be at least 1")

                def show_repack_asset_progress(index: int, total: int, path: Path) -> None:
                    if index == 1 or index == total or index % args.asset_progress_every == 0:
                        print(f"[ASSET {index}/{total}] {path.name}", flush=True)

                asset_report_path = args.output / f"{args.directory.name}.asset_validation.json"
                asset_report = validate_modified_assets(
                    args.directory,
                    args.asset_baseline,
                    asset_report_path,
                    progress=show_repack_asset_progress,
                )
                if asset_report["status"] != "PASS":
                    raise ValueError(
                        f"Asset validation failed; see {asset_report_path.resolve()}"
                    )
                print(
                    f"[PASS] Asset preflight: {asset_report['modified']} modified, "
                    f"{asset_report['warnings']} warning(s)."
                )
            key_bytes = load_key_report(args.key_report) if args.key_report else None
            output, report = repack_archive(args.directory, args.reference, args.output, key_bytes)
            build_report = output.with_suffix(output.suffix + ".build.json")
            build_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                f"[PASS] {report['entry_count']} entries rebuilt: "
                f"{report['modified_entries']} modified, {report['unchanged_entries']} unchanged."
            )
            print(f"[OK] Output: {output.resolve()}")
            print(f"[OK] Validation: {report['validation']}")
        elif args.command == "repack-all":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            if args.asset_baseline is not None:
                asset_report_path = args.report.with_name("asset_validation_before_repack_all.json")

                def show_repack_all_asset_progress(index: int, total: int, path: Path) -> None:
                    if index == 1 or index == total or index % args.progress_every == 0:
                        print(f"[ASSET {index}/{total}] {path.name}", flush=True)

                asset_report = validate_modified_assets(
                    args.workspace,
                    args.asset_baseline,
                    asset_report_path,
                    progress=show_repack_all_asset_progress,
                )
                if asset_report["status"] != "PASS":
                    raise ValueError(
                        f"Asset validation failed; see {asset_report_path.resolve()}"
                    )
                print(
                    f"[PASS] Asset preflight: {asset_report['modified']} modified, "
                    f"{asset_report['warnings']} warning(s)."
                )
            key_bytes = load_key_report(args.key_report) if args.key_report else None
            report = repack_all(
                args.workspace,
                args.references,
                args.output,
                key_bytes,
                args.report,
                progress=lambda event: _show_batch_progress(event, args.progress_every),
                check_space=not args.no_space_check,
                stop_on_error=args.stop_on_error,
            )
            space = report["space_check"]
            print(
                f"\n[SPACE] required={space['required_bytes']} free={space['free_bytes']} "
                f"status={'PASS' if space['passed'] else 'FAIL'}"
            )
            print(
                f"[{report['status']}] rebuilt={report.get('passed_archives', 0)} "
                f"skipped={report.get('skipped_archives', 0)} "
                f"failed={report.get('failed_archives', 0)}"
            )
            print(f"[OK] Report: {args.report.resolve()}")
            return 0 if report["status"] == "PASS" else 1
        elif args.command == "extract-key":
            report = find_ciphercode(args.game_directory)
            save_key_report(report, args.output)
            if not report["found"]:
                print(f"[FAIL] CIPHERCODE not found. Report: {args.output.resolve()}", file=sys.stderr)
                return 1
            print(f"[PASS] CIPHERCODE found ({report['key_size']} bytes).")
            print(f"[OK] Report: {args.output.resolve()}")
        elif args.command == "read-index":
            key_bytes = load_key_report(args.key_report) if args.key_report else None
            report = read_stack_index(args.archive, key_bytes)
            output = args.output or Path("reports") / f"{args.archive.stem}_index.json"
            save_index_report(report, output)
            print(f"[PASS] {report['entry_count']} entries parsed from {args.archive.name}.")
            print(f"[OK] Report: {output.resolve()}")
        elif args.command == "mod-create":
            project = create_mod_project(
                args.directory,
                mod_id=args.id,
                name=args.name,
                author=args.author,
                version=args.version,
                description=args.description,
                target_archives=args.archives,
            )
            print(f"[PASS] Mod project created: {project['name']} {project['version']}")
            print(f"[OK] Project: {args.directory.resolve()}")
        elif args.command == "mod-build":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            output, report = build_mod_package(
                args.project,
                args.workspace,
                args.output,
                progress=lambda index, total, path: _show_mod_progress(
                    index, total, path, args.progress_every
                ),
            )
            print(
                f"[PASS] Mod package: {report['file_count']} modified file(s), "
                f"{len(report['archives'])} archive(s)."
            )
            if report["asset_preflight"] is not None:
                print(
                    f"[PASS] Asset preflight: {report['asset_preflight']['modified']} modified, "
                    f"{report['asset_preflight']['warnings']} warning(s)."
                )
            print(f"[OK] Output: {output.resolve()}")
            print(f"[OK] Build report: {output.with_suffix(output.suffix + '.build.json').resolve()}")
        elif args.command == "mod-inspect":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            report = inspect_mod_package(
                args.package,
                progress=lambda index, total, path: _show_mod_progress(
                    index, total, path, args.progress_every
                ),
            )
            if args.report is not None:
                save_mod_report(report, args.report)
            print(
                f"[PASS] {report['name']} {report['version']}: "
                f"{report['file_count']} file(s), {len(report['archives'])} archive(s)."
            )
            print(f"[OK] Package SHA-256: {report['package_sha256']}")
            if args.report is not None:
                print(f"[OK] Report: {args.report.resolve()}")
        elif args.command == "mod-apply":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            report = apply_mod_package(
                args.package,
                args.workspace,
                progress=lambda index, total, path: _show_mod_progress(
                    index, total, path, args.progress_every
                ),
            )
            save_mod_report(report, args.report)
            print(
                f"[{report['status']}] {report['name']} {report['version']}: "
                f"{report['file_count']} workspace file(s)."
            )
            print(f"[OK] Report: {args.report.resolve()}")
            print("[NEXT] Repack the affected archive(s) using their original GPK references.")
        elif args.command == "mod-remove":
            if args.progress_every < 1:
                raise ValueError("--progress-every must be at least 1")
            report = remove_mod_from_workspace(
                args.mod_id,
                args.workspace,
                progress=lambda index, total, path: _show_mod_progress(
                    index, total, path, args.progress_every
                ),
            )
            save_mod_report(report, args.report)
            print(
                f"[{report['status']}] {args.mod_id}: "
                f"{report.get('restored_files', 0)} file(s) restored."
            )
            print(f"[OK] Report: {args.report.resolve()}")
        return 0
    except (ToolkitError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
