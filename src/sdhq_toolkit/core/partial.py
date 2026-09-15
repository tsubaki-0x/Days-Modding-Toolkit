"""Indexed extraction and restore; no desktop dependencies.

All index entries stay in metadata. Only extracted entries have original hashes.
Existing v0.10 metadata is treated as fully extracted.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from ..formats.gpk.index import read_stack_index
from ..formats.gpk.reader import GPKReader
from ..utils.paths import safe_member_path


def index_identity(report):
    fields = ("path", "offset", "stored_size", "unpacked_size", "header_hex", "unknown_1", "unknown_2", "unknown_3")
    return hashlib.sha256(json.dumps(
        [[entry.get(field) for field in fields] for entry in report["entries"]],
        ensure_ascii=True, separators=(",", ":"),
    ).encode()).hexdigest()


def save_metadata(destination, metadata):
    path = destination / ".sdhq" / "archive.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_metadata(destination):
    path = destination / ".sdhq" / "archive.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def check_reference(metadata, report):
    reference = report.get("archive", metadata.get("source_archive", "GPK"))
    def mismatch(reason):
        return ValueError(
            f"Referência incompatível: {reference}\n{reason}\n"
            f"Origem registrada no workspace: {metadata.get('source_archive', 'não informada')}\n"
            "Use o mesmo GPK utilizado na extração. Para trabalhar com outro GPK, "
            "selecione um novo workspace e preserve as edições da pasta atual."
        )
    if metadata.get("archive_size") != report["archive_size"]:
        raise mismatch(f"Tamanho registrado: {metadata.get('archive_size')} bytes; GPK atual: {report['archive_size']} bytes.")
    if metadata.get("reference_index_sha256"):
        if metadata["reference_index_sha256"] != index_identity(report):
            raise mismatch("O índice atual não corresponde ao registrado na extração.")
    fields = ("path", "offset", "stored_size", "unpacked_size", "header_hex")
    if [[e.get(k) for k in fields] for e in metadata["entries"]] != [
        [e.get(k) for k in fields] for e in report["entries"]
    ]:
        raise mismatch("As entradas do metadata não correspondem ao índice atual.")


def extract_selection(archive: Path, destination: Path, key: bytes, paths=None,
                      *, restore=False, progress=None, cancel=None):
    report = read_stack_index(archive, key)
    entries = report["entries"]
    requested = set(paths) if paths is not None else {e["path"] for e in entries}
    if requested - {e["path"] for e in entries}:
        raise ValueError("Seleção contém entradas ausentes do índice")
    # Validate every destination before creating files (including Windows aliases).
    targets = [safe_member_path(destination, e["path"]) for e in entries]
    if len({str(p).casefold() for p in targets}) != len(targets):
        raise ValueError("Caminhos duplicados no índice")
    metadata = load_metadata(destination)
    if metadata:
        check_reference(metadata, report)
    else:
        metadata = {k: report[k] for k in ("archive_size", "index_size", "index_offset", "entry_count")}
        metadata.update(format="GPK/STACK", source_archive=str(archive.resolve()),
                        source_mtime_ns=archive.stat().st_mtime_ns, streaming=True,
                        entries=[dict(e, extracted=False) for e in entries])
    metadata["metadata_version"] = 2
    metadata["reference_index_sha256"] = index_identity(report)
    selected = [e for e in metadata["entries"] if e["path"] in requested]
    destination.mkdir(parents=True, exist_ok=True)
    try:
        for number, entry in enumerate(selected, 1):
            if cancel:
                cancel.check()
            target = safe_member_path(destination, entry["path"])
            if not restore and entry.get("extracted", True):
                if not target.is_file():
                    raise FileNotFoundError(f"Arquivo extraído ausente; use Restaurar: {target}")
            else:
                if target.exists() and not restore:
                    raise FileExistsError(f"Arquivo não registrado já existe: {target}")
                with tempfile.TemporaryDirectory(prefix="extract-", dir=destination / ".sdhq" if (destination / ".sdhq").is_dir() else destination) as temporary:
                    staging = Path(temporary) / "entry"
                    single = dict(report, entries=[entry], entry_count=1)
                    result = GPKReader(archive, key).extract(staging, index_report=single, cancel=cancel)
                    if cancel:
                        cancel.check()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    safe_member_path(staging, entry["path"]).replace(target)
                    entry.update(result["entries"][0], extracted=True)
            if progress:
                progress(number, len(selected), entry["path"], entry.get("extracted_size", 0))
    finally:
        metadata["extraction_complete"] = all(e.get("extracted", True) for e in metadata["entries"])
        save_metadata(destination, metadata)
    return metadata


def restore_entry(archive, destination, key, path, **kwargs):
    return extract_selection(archive, destination, key, [path], restore=True, **kwargs)
