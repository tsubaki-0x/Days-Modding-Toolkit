"""Project validation and repack helpers from CRio alpha2."""
from .workspace import *  # noqa: F401,F403

def build_project(input_path: Path, project_root: Path) -> dict:
    input_path = input_path.resolve()
    project_root = project_root.resolve()
    if not input_path.exists():
        raise CRioError(f"input does not exist: {input_path}")
    if input_path.is_dir():
        try:
            project_root.relative_to(input_path)
            raise CRioError("project directory must be outside the input tree")
        except ValueError:
            pass
    ensure_new_or_empty_directory(project_root)

    source_kind = "file" if input_path.is_file() else "directory"
    entries: list[dict] = []
    container_count = loose_count = object_count = 0
    for path in iter_files(input_path):
        relative = relative_source_path(input_path, path)
        if is_crio(path):
            parsed = parse_container(path, validate_payloads=True)
            workspace_dir = project_container_dir(project_root, relative)
            extract_container(parsed, relative, workspace_dir)
            workspace_rel = workspace_dir.relative_to(project_root).as_posix()
            entries.append({
                "kind": "crio",
                "source_relative_path": relative.as_posix(),
                "workspace_relative_path": workspace_rel,
                "source_size": parsed.size,
                "source_sha256": parsed.sha256,
                "object_count": len(parsed.objects),
                "repack_supported": parsed.repack_supported,
                "limitations": parsed.limitations,
            })
            container_count += 1
            object_count += len(parsed.objects)
            print(
                f"[CRIO] {relative.as_posix()} | objects={len(parsed.objects)} | "
                f"repack={'yes' if parsed.repack_supported else 'no'}"
            )
        else:
            loose_target = project_root / "LOOSE" / relative
            copy_file_stream(path, loose_target)
            entries.append({
                "kind": "loose",
                "source_relative_path": relative.as_posix(),
                "workspace_relative_path": loose_target.relative_to(project_root).as_posix(),
                "source_size": path.stat().st_size,
                "source_sha256": sha256_file(path),
            })
            loose_count += 1
            print(f"[LOOSE] {relative.as_posix()}")

    project = {
        "format": PROJECT_FORMAT,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_utc": utc_now(),
        "source_kind": source_kind,
        "source_name": input_path.name,
        "container_count": container_count,
        "loose_file_count": loose_count,
        "object_count": object_count,
        "entries": entries,
    }
    write_json(project_root / "_CRIO_PROJECT.json", project)
    (project_root / "REPORTS").mkdir(exist_ok=True)
    print("\n[EXTRACT PASS]")
    print(f"Containers: {container_count}")
    print(f"Loose files: {loose_count}")
    print(f"Objects: {object_count}")
    print(f"Project: {project_root}")
    return project


def load_project(project_root: Path) -> dict:
    project_root = project_root.resolve()
    project = load_json(project_root / "_CRIO_PROJECT.json")
    if project.get("format") != PROJECT_FORMAT:
        raise CRioError("unsupported or invalid CRio project format")
    if project.get("source_kind") not in {"file", "directory"}:
        raise CRioError("project has an invalid source kind")
    entries = project.get("entries")
    if not isinstance(entries, list):
        raise CRioError("project entries are missing or invalid")
    seen_sources: set[str] = set()
    seen_workspaces: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("kind") not in {"crio", "loose"}:
            raise CRioError("project contains an invalid entry")
        source = checked_relative_path(
            entry.get("source_relative_path", ""), "source path"
        ).as_posix()
        workspace = checked_relative_path(
            entry.get("workspace_relative_path", ""), "workspace path"
        ).as_posix()
        source_key = source.casefold()
        workspace_key = workspace.casefold()
        if source_key in seen_sources:
            raise CRioError(f"duplicate source path in project: {source}")
        if workspace_key in seen_workspaces:
            raise CRioError(f"duplicate workspace path in project: {workspace}")
        seen_sources.add(source_key)
        seen_workspaces.add(workspace_key)
    expected_containers = sum(entry["kind"] == "crio" for entry in entries)
    expected_loose = sum(entry["kind"] == "loose" for entry in entries)
    if project.get("container_count") != expected_containers:
        raise CRioError("project container count is inconsistent")
    if project.get("loose_file_count") != expected_loose:
        raise CRioError("project loose-file count is inconsistent")
    return project


def reference_file(reference_root: Path, project: dict, entry: dict) -> Path:
    relative = checked_relative_path(entry["source_relative_path"], "source path")
    if project["source_kind"] == "file":
        return reference_root
    return reference_root / relative


def output_file(output_root: Path, project: dict, entry: dict) -> Path:
    relative = checked_relative_path(entry["source_relative_path"], "source path")
    if project["source_kind"] == "file":
        return output_root
    return output_root / relative


def validate_project(
    project_root: Path,
    reference_root: Path,
    *,
    allow_png_dimension_change: bool = False,
    allow_type_change: bool = False,
) -> dict:
    project_root = project_root.resolve()
    reference_root = reference_root.resolve()
    project = load_project(project_root)
    if project["source_kind"] == "file" and not reference_root.is_file():
        raise CRioError("project expects a single reference file")
    if project["source_kind"] == "directory" and not reference_root.is_dir():
        raise CRioError("project expects a reference directory")

    checked = changed = containers = loose = 0
    issues: list[dict] = []
    changes: list[dict] = []
    for entry in project["entries"]:
        rel = entry["source_relative_path"]
        ref = reference_file(reference_root, project, entry)
        try:
            if not ref.is_file():
                raise CRioError(f"reference file is missing: {ref}")
            if sha256_file(ref) != entry["source_sha256"]:
                raise CRioError(f"reference hash mismatch: {ref}")
            workspace = workspace_entry_path(project_root, entry)
            if entry["kind"] == "loose":
                loose += 1
                if not workspace.is_file():
                    raise CRioError(f"workspace loose file is missing: {workspace}")
                new_hash = sha256_file(workspace)
                if new_hash != entry["source_sha256"]:
                    changed += 1
                    changes.append({"path": rel, "kind": "loose", "sha256": new_hash})
            else:
                containers += 1
                parsed = parse_container(ref, validate_payloads=True)
                manifest = load_json(workspace / "_CRIO" / "manifest.json")
                compare_reference_to_manifest(parsed, manifest)
                extracted_header = workspace / "_CRIO" / "header.bin"
                if not extracted_header.is_file():
                    raise CRioError(f"extracted header is missing: {extracted_header}")
                if (
                    extracted_header.stat().st_size != parsed.header_end
                    or sha256_file(extracted_header) != parsed.header_sha256
                ):
                    raise CRioError(
                        f"extracted header differs from the reference: {extracted_header}"
                    )
                records = records_from_manifest(manifest)
                for current, recorded in zip(parsed.objects, records):
                    if not recorded.workspace_payload:
                        raise CRioError(
                            f"manifest lacks payload path for object {recorded.index}"
                        )
                    payload_path = workspace / checked_relative_path(
                        recorded.workspace_payload, "payload path"
                    )
                    details = validate_payload_file(
                        payload_path,
                        current,
                        allow_png_dimension_change=allow_png_dimension_change,
                        allow_type_change=allow_type_change,
                    )
                    if details["sha256"] != current.payload_sha256:
                        changed += 1
                        changes.append({
                            "path": rel,
                            "kind": "payload",
                            "object_index": current.index,
                            "internal_path": current.internal_path,
                            "old_sha256": current.payload_sha256,
                            "new_sha256": details["sha256"],
                        })
            checked += 1
        except Exception as exc:
            issues.append({"path": rel, "error": str(exc)})

    report = {
        "format": "days-crio-validation-v1",
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_utc": utc_now(),
        "project": str(project_root),
        "reference": str(reference_root),
        "checked_entries": checked,
        "containers": containers,
        "loose_files": loose,
        "changed_items": changed,
        "changes": changes,
        "issues": issues,
        "all_checks_pass": not issues,
    }
    report_path = project_root / "REPORTS" / "validation_report.json"
    write_json(report_path, report)
    if issues:
        lines = []
        for issue in issues[:5]:
            path = issue.get("path") or "<unknown>"
            error = issue.get("error") or "unknown validation error"
            lines.append(f"{path}: {error}")
        if len(issues) > 5:
            lines.append(f"... and {len(issues) - 5} more issue(s)")
        detail = "\n".join(lines)
        raise CRioError(
            f"validation failed with {len(issues)} issue(s):\n"
            f"{detail}\n"
            f"Report: {report_path}"
        )
    print("[VALIDATION PASS]")
    print(f"Entries: {checked}")
    print(f"Containers: {containers}")
    print(f"Loose files: {loose}")
    print(f"Modified payload/files: {changed}")
    return report


def repack_project(
    project_root: Path,
    reference_root: Path,
    output_root: Path,
    *,
    allow_png_dimension_change: bool,
    allow_type_change: bool,
    overwrite: bool,
) -> dict:
    project_root = project_root.resolve()
    reference_root = reference_root.resolve()
    output_root = output_root.resolve()
    project = load_project(project_root)
    assert_distinct_paths(reference_root, output_root, "output")
    assert_distinct_paths(project_root, output_root, "output")
    if output_root.is_relative_to(project_root):
        raise CRioError("output must be outside the extracted project")
    if (
        project["source_kind"] == "directory"
        and output_root.is_relative_to(reference_root)
    ):
        raise CRioError("directory output must be outside the reference tree")
    validate_project(
        project_root,
        reference_root,
        allow_png_dimension_change=allow_png_dimension_change,
        allow_type_change=allow_type_change,
    )

    if project["source_kind"] == "directory":
        if output_root.exists():
            if not output_root.is_dir():
                raise CRioError("directory output path exists and is not a directory")
            if any(output_root.iterdir()):
                raise CRioError("directory output must not exist or must be empty")
        output_root.mkdir(parents=True, exist_ok=True)
    else:
        output_root.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for entry in project["entries"]:
        ref = reference_file(reference_root, project, entry)
        out = output_file(output_root, project, entry)
        workspace = workspace_entry_path(project_root, entry)
        if entry["kind"] == "loose":
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() and not overwrite:
                raise CRioError(f"output already exists: {out}")
            copy_file_stream(workspace, out)
            result = {
                "source": str(ref),
                "output": str(out),
                "kind": "loose",
                "source_sha256": entry["source_sha256"],
                "output_sha256": sha256_file(out),
                "changed": sha256_file(out) != entry["source_sha256"],
            }
            results.append(result)
            print(f"[LOOSE] {entry['source_relative_path']}")
        else:
            parsed = parse_container(ref, validate_payloads=True)
            manifest = load_json(workspace / "_CRIO" / "manifest.json")
            result = rebuild_container(
                parsed,
                manifest,
                workspace,
                out,
                allow_png_dimension_change=allow_png_dimension_change,
                allow_type_change=allow_type_change,
                overwrite=overwrite,
            )
            result["kind"] = "crio"
            result["source_relative_path"] = entry["source_relative_path"]
            results.append(result)
            print(
                f"[CRIO] {entry['source_relative_path']} | "
                f"changed={result['changed_payload_count']} | "
                f"roundtrip={'yes' if result['byte_identical'] else 'modified'}"
            )

    report = {
        "format": "days-crio-repack-report-v1",
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_utc": utc_now(),
        "project": str(project_root),
        "reference": str(reference_root),
        "output": str(output_root),
        "entries": results,
        "container_count": sum(r["kind"] == "crio" for r in results),
        "loose_file_count": sum(r["kind"] == "loose" for r in results),
        "changed_container_count": sum(
            r["kind"] == "crio" and not r["byte_identical"] for r in results
        ),
        "all_checks_pass": True,
    }
    write_json(project_root / "REPORTS" / "repack_report.json", report)
    print("\n[REPACK PASS]")
    print(f"Output: {output_root}")
    return report
