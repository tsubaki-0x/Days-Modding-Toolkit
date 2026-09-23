"""Workspace extraction and container rebuild helpers from CRio alpha2."""
from .parser import *  # noqa: F401,F403

def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().casefold()):
        if path.is_file():
            yield path


def relative_source_path(root: Path, path: Path) -> Path:
    return Path(path.name) if root.is_file() else path.relative_to(root)


def ensure_new_or_empty_directory(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise CRioError(f"destination exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise CRioError(f"destination directory is not empty: {path}")
    else:
        path.mkdir(parents=True)


def assert_distinct_paths(a: Path, b: Path, label: str) -> None:
    if a.resolve() == b.resolve():
        raise CRioError(f"{label} must not overwrite its reference/input: {a}")


def checked_relative_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CRioError(f"missing or invalid {label} in project manifest")
    path = Path(value)
    if (
        path == Path(".")
        or path.is_absolute()
        or any(part == ".." for part in path.parts)
    ):
        raise CRioError(f"unsafe {label} in project manifest: {value!r}")
    return path


def project_container_dir(project_root: Path, source_relative: Path) -> Path:
    parts = [fs_safe_component(part) for part in source_relative.parts]
    return project_root.joinpath("CONTAINERS", *parts)


def choose_payload_paths(container: ParsedContainer) -> None:
    used: set[str] = set()
    for obj in container.objects:
        lineage: list[str] = []
        current: Optional[ObjectRecord] = obj
        while current is not None:
            lineage.append(fs_safe_component(current.name))
            current = (
                container.objects[current.parent_index]
                if current.parent_index is not None
                else None
            )
        natural = Path("TREE", *reversed(lineage))
        key = natural.as_posix().casefold()
        if obj.child_count == 0 and key not in used:
            obj.workspace_payload = natural.as_posix()
            obj.storage_kind = "tree"
            used.add(key)
        else:
            raw = Path("_CRIO", "OBJECT_PAYLOADS", f"{obj.index:06d}.bin")
            obj.workspace_payload = raw.as_posix()
            obj.storage_kind = "object_payload"


def container_manifest(container: ParsedContainer, source_relative: Path) -> dict:
    return {
        "format": PROJECT_FORMAT,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_utc": utc_now(),
        "source_relative_path": source_relative.as_posix(),
        "source_size": container.size,
        "source_sha256": container.sha256,
        "root_count": container.root_count,
        "header_end": container.header_end,
        "header_sha256": container.header_sha256,
        "object_count": len(container.objects),
        "repack_supported": container.repack_supported,
        "limitations": container.limitations,
        "objects": [asdict(obj) for obj in container.objects],
    }


def extract_container(container: ParsedContainer, source_relative: Path, destination: Path) -> dict:
    choose_payload_paths(container)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_dir = destination / "_CRIO"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    with container.path.open("rb") as src:
        src.seek(0)
        header = src.read(container.header_end)
        (metadata_dir / "header.bin").write_bytes(header)
        for obj in container.objects:
            target = destination / obj.workspace_payload
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                copy_region(src, out, obj.payload_offset, obj.payload_size)

    manifest = container_manifest(container, source_relative)
    manifest_path = metadata_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "source_relative_path": source_relative.as_posix(),
        "workspace_relative_path": destination.as_posix(),
        "source_size": container.size,
        "source_sha256": container.sha256,
        "object_count": len(container.objects),
        "repack_supported": container.repack_supported,
        "limitations": container.limitations,
    }


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CRioError(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def workspace_entry_path(project_root: Path, entry: dict) -> Path:
    relative = checked_relative_path(
        entry["workspace_relative_path"], "workspace path"
    )
    return project_root / relative


def validate_payload_file(
    path: Path,
    expected: ObjectRecord,
    *,
    allow_png_dimension_change: bool,
    allow_type_change: bool,
) -> dict:
    if not path.is_file():
        raise CRioError(f"payload file is missing: {path}")
    size = path.stat().st_size
    if size > MAX_PAYLOAD_SIZE:
        raise CRioError(
            f"replacement payload exceeds the CRio uint32 range: {path} ({size} bytes)"
        )
    with path.open("rb") as fh:
        sample = fh.read(min(size, 65536))
    detected = detect_type(sample, expected.class_declared)
    if not allow_type_change and detected != expected.payload_type:
        raise CRioError(
            f"payload type changed for {expected.internal_path!r}: "
            f"{expected.payload_type} -> {detected} ({path})"
        )
    details = {
        "size": size,
        "sha256": sha256_file(path),
        "detected_type": detected,
        "png_width": None,
        "png_height": None,
    }
    if detected == "PNG":
        exact, width, height = parse_png_file(path)
        if exact != size:
            raise CRioError(f"PNG contains bytes after IEND: {path}")
        details["png_width"] = width
        details["png_height"] = height
        old_dimensions = (expected.png_width, expected.png_height)
        if (
            not allow_png_dimension_change
            and old_dimensions != (width, height)
        ):
            raise CRioError(
                f"PNG dimensions changed for {expected.internal_path!r}: "
                f"{old_dimensions[0]}x{old_dimensions[1]} -> {width}x{height}"
            )
    elif detected == "FOLDER":
        if path.read_bytes() != FOLDER_PAYLOAD:
            raise CRioError(f"CAutoFolder payload was modified incompatibly: {path}")
    return details


def records_from_manifest(manifest: dict) -> list[ObjectRecord]:
    return [ObjectRecord(**item) for item in manifest["objects"]]


def compare_reference_to_manifest(container: ParsedContainer, manifest: dict) -> None:
    if container.sha256 != manifest["source_sha256"]:
        raise CRioError(
            f"reference SHA-256 mismatch for {manifest['source_relative_path']}: "
            f"expected {manifest['source_sha256']}, got {container.sha256}"
        )
    if container.header_sha256 != manifest["header_sha256"]:
        raise CRioError("reference header differs from extraction manifest")
    old_records = records_from_manifest(manifest)
    if len(container.objects) != len(old_records):
        raise CRioError("reference object count differs from extraction manifest")
    for current, old in zip(container.objects, old_records):
        identity_current = (
            current.index,
            current.parent_index,
            current.name_raw_hex,
            current.class_tag,
            current.class_declared,
            current.child_count,
            current.internal_path,
        )
        identity_old = (
            old.index,
            old.parent_index,
            old.name_raw_hex,
            old.class_tag,
            old.class_declared,
            old.child_count,
            old.internal_path,
        )
        if identity_current != identity_old:
            raise CRioError(f"reference tree differs at object {current.index}")


def rebuild_container(
    reference: ParsedContainer,
    manifest: dict,
    container_workspace: Path,
    output: Path,
    *,
    allow_png_dimension_change: bool,
    allow_type_change: bool,
    overwrite: bool,
) -> dict:
    if not reference.repack_supported:
        raise CRioError(
            "container uses an unproven payload size encoding and cannot be repacked safely"
        )
    compare_reference_to_manifest(reference, manifest)
    manifest_records = records_from_manifest(manifest)
    payloads: list[tuple[ObjectRecord, Path, dict]] = []
    changed: list[dict] = []
    position = reference.header_end

    with reference.path.open("rb") as src:
        header = bytearray(src.read(reference.header_end))

    for current, recorded in zip(reference.objects, manifest_records):
        if not recorded.workspace_payload:
            raise CRioError(f"manifest lacks payload path for object {recorded.index}")
        payload_path = container_workspace / checked_relative_path(
            recorded.workspace_payload, "payload path"
        )
        details = validate_payload_file(
            payload_path,
            current,
            allow_png_dimension_change=allow_png_dimension_change,
            allow_type_change=allow_type_change,
        )
        struct.pack_into(
            "<I", header, current.encoded_offset_field, encode_offset(position)
        )
        struct.pack_into(
            "<I", header, current.encoded_size_field, encode_size(details["size"])
        )
        payloads.append((current, payload_path, details))
        if details["sha256"] != current.payload_sha256:
            changed.append({
                "index": current.index,
                "internal_path": current.internal_path,
                "payload_type": current.payload_type,
                "old_size": current.payload_size,
                "new_size": details["size"],
                "old_sha256": current.payload_sha256,
                "new_sha256": details["sha256"],
                "old_dimensions": [current.png_width, current.png_height]
                    if current.payload_type == "PNG" else None,
                "new_dimensions": [details["png_width"], details["png_height"]]
                    if details["detected_type"] == "PNG" else None,
            })
        position += details["size"]

    if position > MASK32:
        raise CRioError(
            f"rebuilt container would exceed the confirmed 32-bit file range: "
            f"0x{position:X} bytes"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        raise CRioError(f"output already exists (use --overwrite): {output}")
    fd, temp_name = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("wb") as out:
            out.write(header)
            for _, payload_path, _ in payloads:
                with payload_path.open("rb") as inp:
                    shutil.copyfileobj(inp, out, length=8 * 1024 * 1024)

        parsed_output = parse_container(temp_path, validate_payloads=True)
        if len(parsed_output.objects) != len(reference.objects):
            raise CRioError("rebuilt object count differs from reference")
        for before, after in zip(reference.objects, parsed_output.objects):
            if (
                before.name_raw_hex,
                before.parent_index,
                before.child_count,
                before.class_tag,
                before.class_declared,
            ) != (
                after.name_raw_hex,
                after.parent_index,
                after.child_count,
                after.class_tag,
                after.class_declared,
            ):
                raise CRioError(f"rebuilt tree differs at object {before.index}")
        os.replace(temp_path, output)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass

    output_hash = sha256_file(output)
    if not changed and output_hash != reference.sha256:
        raise CRioError(
            "no payload changed, but rebuilt container is not byte-identical"
        )
    return {
        "source": str(reference.path),
        "output": str(output),
        "source_sha256": reference.sha256,
        "output_sha256": output_hash,
        "source_size": reference.size,
        "output_size": output.stat().st_size,
        "object_count": len(reference.objects),
        "changed_payload_count": len(changed),
        "changed_payloads": changed,
        "byte_identical": output_hash == reference.sha256,
    }
