from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .asset_validation import validate_modified_assets
from ..utils.hashing import sha256_file
from ..utils.paths import safe_member_path


MOD_MANIFEST_VERSION = 1
MOD_FORMAT = "School Days HQ Mod Package"
PROJECT_FORMAT = "School Days HQ Mod Project"
MOD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,31}$")
MANIFEST_MAX_BYTES = 1024 * 1024
STREAM_CHUNK_SIZE = 1024 * 1024
ModProgress = Callable[[int, int, str], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(path: Path, payload: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_mod_report(report: dict, path: Path) -> None:
    """Save a mod operation report without risking a partially written JSON file."""
    _write_json_atomic(path, report)


def _validate_identity(mod_id: str, version: str) -> None:
    if not MOD_ID_PATTERN.fullmatch(mod_id):
        raise ValueError(
            "Mod id must contain 3-64 lowercase letters, numbers, dots, underscores or hyphens"
        )
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("Mod version contains unsupported characters")


def _validate_relative_path(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"Invalid {label}: {value!r}")
    normalized = PurePosixPath(value)
    if normalized.is_absolute() or "." in normalized.parts or ".." in normalized.parts:
        raise ValueError(f"Unsafe {label}: {value!r}")
    return normalized.as_posix()


def _validate_archive_name(value: str) -> str:
    value = _validate_relative_path(value, label="archive name")
    if "/" in value:
        raise ValueError(f"Archive name cannot contain directories: {value}")
    return value


def create_mod_project(
    directory: Path,
    *,
    mod_id: str,
    name: str,
    author: str,
    version: str,
    description: str = "",
    target_archives: list[str] | None = None,
) -> dict:
    _validate_identity(mod_id, version)
    if not name.strip() or not author.strip():
        raise ValueError("Mod name and author cannot be empty")
    archives = []
    seen: set[str] = set()
    for archive in target_archives or []:
        archive = _validate_archive_name(archive)
        normalized = archive.lower()
        if normalized in seen:
            raise ValueError(f"Duplicate target archive: {archive}")
        seen.add(normalized)
        archives.append(archive)

    directory = directory.resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise FileExistsError(f"Mod project directory is not empty: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    project = {
        "format": PROJECT_FORMAT,
        "project_version": 1,
        "id": mod_id,
        "name": name.strip(),
        "author": author.strip(),
        "version": version,
        "description": description.strip(),
        "game": "School Days HQ",
        "game_version": "1.02",
        "target_archives": archives,
    }
    _write_json_atomic(directory / "mod.json", project)
    readme = directory / "README.txt"
    readme.write_text(
        "Edite os arquivos dentro do workspace do toolkit.\n"
        "Depois use build_mod_package.py com este projeto e o workspace.\n"
        "O pacote final incluirá somente os arquivos detectados como modificados.\n",
        encoding="utf-8",
    )
    return project


def _load_project(directory: Path) -> dict:
    path = directory.resolve() / "mod.json"
    try:
        project = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid mod project JSON: {path}") from exc
    if project.get("format") != PROJECT_FORMAT or project.get("project_version") != 1:
        raise ValueError("Unsupported mod project format or version")
    for field in ("id", "name", "author", "version", "game", "game_version"):
        if not isinstance(project.get(field), str) or not project[field]:
            raise ValueError(f"Mod project is missing a valid {field!r}")
    _validate_identity(project["id"], project["version"])
    if project["game"] != "School Days HQ" or project["game_version"] != "1.02":
        raise ValueError("This toolkit currently builds mods only for School Days HQ v1.02")
    targets = project.get("target_archives", [])
    if not isinstance(targets, list):
        raise ValueError("target_archives must be a list")
    for archive in targets:
        _validate_archive_name(archive)
    return project


def _workspace_archives(workspace: Path) -> dict[str, tuple[Path, dict]]:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace not found: {workspace}")
    result: dict[str, tuple[Path, dict]] = {}
    for directory in sorted(workspace.iterdir(), key=lambda path: path.name.lower()):
        metadata_path = directory / ".sdhq" / "archive.json"
        if not directory.is_dir() or not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid extraction metadata: {metadata_path}") from exc
        if metadata.get("format") != "GPK/STACK" or not isinstance(metadata.get("entries"), list):
            raise ValueError(f"Unsupported extraction metadata: {metadata_path}")
        normalized = directory.name.lower()
        if normalized in result:
            raise ValueError(f"Duplicate workspace archive name: {directory.name}")
        result[normalized] = (directory, metadata)
    if not result:
        raise FileNotFoundError(f"No completed GPK workspaces found in: {workspace}")
    return result


def _zip_info(name: str, compress_type: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = compress_type
    info.external_attr = 0o100644 << 16
    return info


def _asset_compression(path: str) -> int:
    if Path(path).suffix.lower() in {".png", ".ogg", ".wmv", ".jpg", ".jpeg", ".mp3", ".zip"}:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def _copy_into_zip(archive: zipfile.ZipFile, info: zipfile.ZipInfo, source: Path) -> None:
    with source.open("rb") as input_stream, archive.open(info, "w") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, STREAM_CHUNK_SIZE)


def build_mod_package(
    project_directory: Path,
    workspace: Path,
    output_directory: Path,
    *,
    asset_baseline: Path | None = None,
    allow_unknown: bool = False,
    progress: ModProgress | None = None,
    preview_only: bool = False,
    expected_files: list[dict] | None = None,
) -> tuple[Path, dict]:
    project = _load_project(project_directory)
    archives = _workspace_archives(workspace)
    requested = project.get("target_archives") or [value[0].name for value in archives.values()]
    selected: list[tuple[Path, dict]] = []
    for name in requested:
        item = archives.get(name.lower())
        if item is None:
            raise FileNotFoundError(f"Target archive is not extracted in the workspace: {name}")
        selected.append(item)

    asset_preflight = None
    if asset_baseline is not None:
        validation_reports = [
            validate_modified_assets(
                directory,
                asset_baseline,
                None,
                allow_unknown=allow_unknown,
            )
            for directory, _ in selected
        ]
        failed = sum(report["failed"] for report in validation_reports)
        if failed:
            details = "; ".join(
                f"{directory.name}: {report['failed']} failure(s)"
                for (directory, _), report in zip(selected, validation_reports)
                if report["failed"]
            )
            raise ValueError(f"Mod asset preflight failed: {details}")
        asset_preflight = {
            "status": "PASS",
            "baseline_sha256": sha256_file(asset_baseline),
            "modified": sum(report["modified"] for report in validation_reports),
            "warnings": sum(report["warnings"] for report in validation_reports),
            "allow_unknown": allow_unknown,
        }

    total_entries = sum(len(metadata["entries"]) for _, metadata in selected)
    current_index = 0
    files: list[dict] = []
    archive_descriptions: list[dict] = []
    source_paths: dict[str, Path] = {}
    for directory, metadata in selected:
        declared_paths: set[Path] = set()
        archive_descriptions.append(
            {
                "archive": directory.name,
                "source_archive": Path(metadata.get("source_archive", directory.name + ".gpk")).name,
                "reference_size": metadata.get("archive_size"),
                "entry_count": len(metadata["entries"]),
            }
        )
        for entry in metadata["entries"]:
            current_index += 1
            relative = _validate_relative_path(entry.get("path"), label="GPK entry path")
            asset = safe_member_path(directory, relative)
            declared_paths.add(asset.resolve())
            if progress is not None:
                progress(current_index, total_entries, f"{directory.name}/{relative}")
            if not entry.get("extracted", True):
                if asset.exists():
                    raise ValueError(f"Untracked file at unextracted entry: {asset}")
                continue
            if not asset.is_file() or asset.is_symlink():
                raise FileNotFoundError(f"Missing or unsupported workspace file: {asset}")
            original_hash = entry.get("extracted_sha256")
            if not isinstance(original_hash, str) or len(original_hash) != 64:
                raise ValueError(f"Extraction metadata has no original hash: {asset}")
            current_hash = sha256_file(asset)
            if current_hash == original_hash:
                continue
            member = f"files/{directory.name}/{relative}"
            files.append(
                {
                    "archive": directory.name,
                    "path": relative,
                    "member": member,
                    "size_bytes": asset.stat().st_size,
                    "original_sha256": original_hash,
                    "modified_sha256": current_hash,
                }
            )
            source_paths[member] = asset

        for asset in directory.rglob("*"):
            if not asset.is_file() or ".sdhq" in asset.relative_to(directory).parts:
                continue
            if asset.resolve() not in declared_paths:
                raise ValueError(f"New GPK entries are not supported: {asset}")

    if not files:
        raise ValueError("No modified workspace files were found for this mod project")
    files.sort(key=lambda item: (item["archive"].lower(), item["path"].lower(), item["path"]))
    if expected_files is not None and files != expected_files:
        raise ValueError("Workspace changed since package preview; preview again")
    if preview_only:
        return output_directory, {"files": files, "file_count": len(files), "status": "PREVIEW"}
    manifest = {
        "format": MOD_FORMAT,
        "manifest_version": MOD_MANIFEST_VERSION,
        "id": project["id"],
        "name": project["name"],
        "author": project["author"],
        "version": project["version"],
        "description": project.get("description", ""),
        "game": "School Days HQ",
        "game_version": "1.02",
        "toolkit_version": "0.11.0-dev",
        "built_at": _utc_now(),
        "archives": archive_descriptions,
        "asset_preflight": asset_preflight,
        "file_count": len(files),
        "files": files,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"{project['id']}-{project['version']}.sdmod"
    temporary = output.with_name(output.name + ".tmp")
    if output.exists() or temporary.exists():
        raise FileExistsError(f"Package output already exists: {output}")
    try:
        with zipfile.ZipFile(temporary, "x", allowZip64=True) as archive:
            archive.writestr(_zip_info("mod.json", zipfile.ZIP_DEFLATED), manifest_bytes)
            for number, item in enumerate(files, 1):
                if progress:
                    progress(number, len(files), item["member"])
                member = item["member"]
                _copy_into_zip(archive, _zip_info(member, _asset_compression(item["path"])), source_paths[member])
        verified = inspect_mod_package(temporary, progress=progress)
        if verified["file_count"] != len(files):
            raise ValueError("Package verification failed")
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    inspection = inspect_mod_package(output)
    report = {
        "format": "School Days HQ mod build report",
        "status": "PASS",
        "project": str(project_directory.resolve()),
        "workspace": str(workspace.resolve()),
        "output": str(output),
        "package_sha256": inspection["package_sha256"],
        "package_size": output.stat().st_size,
        "file_count": len(files),
        "archives": sorted({item["archive"] for item in files}, key=str.lower),
        "asset_preflight": asset_preflight,
        "files": files,
    }
    _write_json_atomic(output.with_suffix(output.suffix + ".build.json"), report)
    return output, report


def _read_manifest(archive: zipfile.ZipFile) -> dict:
    try:
        info = archive.getinfo("mod.json")
    except KeyError as exc:
        raise ValueError("Mod package has no mod.json manifest") from exc
    if info.file_size > MANIFEST_MAX_BYTES:
        raise ValueError("Mod manifest is unreasonably large")
    try:
        manifest = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Mod manifest is not valid UTF-8 JSON") from exc
    return manifest


def _validate_manifest(manifest: dict) -> list[dict]:
    if manifest.get("format") != MOD_FORMAT or manifest.get("manifest_version") != MOD_MANIFEST_VERSION:
        raise ValueError("Unsupported mod package format or manifest version")
    for field in ("id", "name", "author", "version", "game", "game_version"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ValueError(f"Mod manifest is missing a valid {field!r}")
    _validate_identity(manifest["id"], manifest["version"])
    if manifest["game"] != "School Days HQ" or manifest["game_version"] != "1.02":
        raise ValueError("Mod package targets an unsupported game or game version")
    archives = manifest.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ValueError("Mod manifest has no archive descriptions")
    described_archives: set[str] = set()
    for item in archives:
        if not isinstance(item, dict):
            raise ValueError("Mod archive description must be an object")
        archive = _validate_archive_name(item.get("archive"))
        normalized = archive.lower()
        if normalized in described_archives:
            raise ValueError(f"Duplicate archive description: {archive}")
        described_archives.add(normalized)
    files = manifest.get("files")
    if not isinstance(files, list) or not files or manifest.get("file_count") != len(files):
        raise ValueError("Mod manifest has an invalid file list or count")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Mod file entry must be an object")
        archive = _validate_archive_name(item.get("archive"))
        if archive.lower() not in described_archives:
            raise ValueError(f"Mod file refers to an undescribed archive: {archive}")
        path = _validate_relative_path(item.get("path"), label="mod file path")
        expected_member = f"files/{archive}/{path}"
        if item.get("member") != expected_member:
            raise ValueError(f"Mod member does not match its archive/path: {item.get('member')}")
        normalized = expected_member.lower()
        if normalized in seen:
            raise ValueError(f"Duplicate or case-colliding mod member: {expected_member}")
        seen.add(normalized)
        if not isinstance(item.get("size_bytes"), int) or item["size_bytes"] < 0:
            raise ValueError(f"Invalid size for mod member: {expected_member}")
        for field in ("original_sha256", "modified_sha256"):
            value = item.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"Invalid {field} for mod member: {expected_member}")
            if field == "modified_sha256" and value == item["original_sha256"]:
                raise ValueError(f"Mod member is not actually modified: {expected_member}")
    return files


def _hash_zip_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as stream:
        while chunk := stream.read(STREAM_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_mod_package(package: Path, *, progress: ModProgress | None = None) -> dict:
    package = package.resolve()
    if not package.is_file():
        raise FileNotFoundError(f"Mod package not found: {package}")
    with zipfile.ZipFile(package, "r") as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names: set[str] = set()
        normalized_names: set[str] = set()
        for info in infos:
            name = _validate_relative_path(info.filename, label="ZIP member")
            if info.flag_bits & 1:
                raise ValueError(f"Encrypted ZIP members are unsupported: {name}")
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError(f"Symbolic links are unsupported in mod packages: {name}")
            if name in names or name.lower() in normalized_names:
                raise ValueError(f"Duplicate or case-colliding ZIP member: {name}")
            names.add(name)
            normalized_names.add(name.lower())
        manifest = _read_manifest(archive)
        files = _validate_manifest(manifest)
        expected_names = {"mod.json", *(item["member"] for item in files)}
        if names != expected_names:
            missing = sorted(expected_names - names)
            extra = sorted(names - expected_names)
            raise ValueError(f"Mod package member mismatch; missing={missing}, extra={extra}")
        for index, item in enumerate(files, start=1):
            if progress is not None:
                progress(index, len(files), item["member"])
            info = archive.getinfo(item["member"])
            if info.file_size != item["size_bytes"]:
                raise ValueError(f"Size mismatch in mod member: {item['member']}")
            if _hash_zip_member(archive, info) != item["modified_sha256"]:
                raise ValueError(f"SHA-256 mismatch in mod member: {item['member']}")
    return {
        "format": "School Days HQ mod inspection",
        "status": "PASS",
        "package": str(package),
        "package_sha256": sha256_file(package),
        "package_size": package.stat().st_size,
        "id": manifest["id"],
        "name": manifest["name"],
        "author": manifest["author"],
        "version": manifest["version"],
        "game_version": manifest["game_version"],
        "file_count": len(files),
        "total_file_bytes": sum(item["size_bytes"] for item in files),
        "archives": sorted({item["archive"] for item in files}, key=str.lower),
        "files": files,
        "manifest": manifest,
    }


def _copy_zip_member_atomic(archive: zipfile.ZipFile, member: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".sdhq-mod-part")
    if temporary.exists():
        raise FileExistsError(f"Temporary mod file already exists: {temporary}")
    try:
        with archive.open(member, "r") as source, temporary.open("xb") as output:
            shutil.copyfileobj(source, output, STREAM_CHUNK_SIZE)
        temporary.replace(destination)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def _state_paths(workspace: Path, mod_id: str) -> tuple[Path, Path]:
    root = workspace.resolve() / ".sdhq" / "mods" / mod_id
    return root, root / "state.json"


def apply_mod_package(
    package: Path,
    workspace: Path,
    *,
    progress: ModProgress | None = None,
) -> dict:
    inspection = inspect_mod_package(package)
    workspace = workspace.resolve()
    archives = _workspace_archives(workspace)
    state_root, state_path = _state_paths(workspace, inspection["id"])
    package_hash = inspection["package_sha256"]
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("installed"):
            if state.get("package_sha256") == package_hash:
                return {**state, "status": "ALREADY_APPLIED"}
            raise ValueError(
                f"Another installed version of mod {inspection['id']!r} already has state data"
            )

    resolved: list[tuple[dict, Path, Path]] = []
    for item in inspection["files"]:
        archive_item = archives.get(item["archive"].lower())
        if archive_item is None:
            raise FileNotFoundError(f"Required archive workspace is missing: {item['archive']}")
        directory, metadata = archive_item
        original_entries = {entry["path"]: entry for entry in metadata["entries"]}
        metadata_entry = original_entries.get(item["path"])
        if metadata_entry is None:
            raise ValueError(f"Mod targets an entry absent from the original GPK: {item['member']}")
        if metadata_entry.get("extracted_sha256") != item["original_sha256"]:
            raise ValueError(f"Mod is incompatible with the extracted game file: {item['member']}")
        target = safe_member_path(directory, item["path"])
        if not target.is_file() or target.is_symlink():
            raise FileNotFoundError(f"Mod target is missing or unsupported: {target}")
        current_hash = sha256_file(target)
        if current_hash != item["original_sha256"]:
            raise ValueError(f"Mod conflict: workspace target is not clean: {item['member']}")
        backup = safe_member_path(state_root / "backup" / item["archive"], item["path"])
        if backup.exists() and sha256_file(backup) != item["original_sha256"]:
            raise ValueError(f"Existing mod backup has the wrong hash: {backup}")
        resolved.append((item, target, backup))

    state_root.mkdir(parents=True, exist_ok=True)
    applied: list[tuple[Path, Path]] = []
    try:
        with zipfile.ZipFile(package.resolve(), "r") as archive:
            for index, (item, target, backup) in enumerate(resolved, start=1):
                if progress is not None:
                    progress(index, len(resolved), item["member"])
                if not backup.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    temporary_backup = backup.with_name(backup.name + ".tmp")
                    shutil.copy2(target, temporary_backup)
                    temporary_backup.replace(backup)
                _copy_zip_member_atomic(archive, item["member"], target)
                applied.append((target, backup))
                if sha256_file(target) != item["modified_sha256"]:
                    raise ValueError(f"Applied mod file failed hash verification: {item['member']}")
    except Exception:
        for target, backup in reversed(applied):
            shutil.copy2(backup, target)
        raise

    state = {
        "format": "School Days HQ installed workspace mod state",
        "state_version": 1,
        "installed": True,
        "status": "PASS",
        "id": inspection["id"],
        "name": inspection["name"],
        "version": inspection["version"],
        "package": str(package.resolve()),
        "package_sha256": package_hash,
        "workspace": str(workspace),
        "applied_at": _utc_now(),
        "file_count": len(resolved),
        "archives": inspection["archives"],
        "files": inspection["files"],
    }
    _write_json_atomic(state_path, state)
    return state


def remove_mod_from_workspace(
    mod_id: str,
    workspace: Path,
    *,
    progress: ModProgress | None = None,
) -> dict:
    _validate_identity(mod_id, "1")
    workspace = workspace.resolve()
    state_root, state_path = _state_paths(workspace, mod_id)
    if not state_path.is_file():
        raise FileNotFoundError(f"No mod state found for: {mod_id}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("format") != "School Days HQ installed workspace mod state":
        raise ValueError(f"Unsupported mod state: {state_path}")
    if not state.get("installed"):
        return {**state, "status": "NOT_INSTALLED"}
    archives = _workspace_archives(workspace)
    resolved: list[tuple[dict, Path, Path, bool]] = []
    for item in state.get("files", []):
        archive_item = archives.get(item["archive"].lower())
        if archive_item is None:
            raise FileNotFoundError(f"Required archive workspace is missing: {item['archive']}")
        target = safe_member_path(archive_item[0], item["path"])
        backup = safe_member_path(state_root / "backup" / item["archive"], item["path"])
        if not backup.is_file() or sha256_file(backup) != item["original_sha256"]:
            raise ValueError(f"Cannot restore invalid or missing mod backup: {backup}")
        if not target.is_file() or target.is_symlink():
            raise FileNotFoundError(f"Installed mod target is missing: {target}")
        current_hash = sha256_file(target)
        if current_hash == item["original_sha256"]:
            needs_restore = False
        elif current_hash == item["modified_sha256"]:
            needs_restore = True
        else:
            raise ValueError(f"Cannot remove mod over a later workspace modification: {item['member']}")
        resolved.append((item, target, backup, needs_restore))

    for index, (item, target, backup, needs_restore) in enumerate(resolved, start=1):
        if progress is not None:
            progress(index, len(resolved), item["member"])
        if needs_restore:
            temporary = target.with_name(target.name + ".sdhq-restore-part")
            shutil.copy2(backup, temporary)
            temporary.replace(target)
    state.update(
        {
            "installed": False,
            "status": "PASS",
            "removed_at": _utc_now(),
            "restored_files": sum(item[3] for item in resolved),
        }
    )
    _write_json_atomic(state_path, state)
    return state
