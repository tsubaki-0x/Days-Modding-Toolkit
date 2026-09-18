"""Application service for the desktop. All archive work stays outside widgets."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from .asset_validation import _format_name, _inspect_asset, _compare_properties
from .key_extractor import find_ciphercode
from .partial import extract_selection, load_metadata, restore_entry, check_reference
from .repacker import repack_archive
from . import mods
from ..formats.gpk.index import read_stack_index
from ..formats.gpk.reader import GPKReader
from ..utils.hashing import sha256_file
from ..utils.paths import safe_member_path


STATES = ("original", "modificado", "ausente", "novo", "inválido", "não extraído", "não verificado")
RULES = {
    "PNG": "Preservar dimensões, transparência, profundidade e tipo de cor.",
    "Ogg": "Preservar codec, canais e frequência de amostragem.",
    "ASF/WMV": "Preservar streams, codecs, resolução e duração; conferir avisos de duração.",
    "CMAP": "Preservar dimensões e IDs de regiões do original.",
    "ORS": "Preservar codificação, seções, comandos e estrutura do script. Validação semântica não disponível.",
    "INI": "Preservar codificação, seções e chaves.",
    "TXT": "Preservar codificação e estrutura esperada pelo jogo.",
}


class ValidationBlocked(ValueError):
    def __init__(self, report):
        self.report = report
        details = "\n".join(f"{item['archive']}/{item['path']}: {item['reason']}" for item in report["errors"])
        super().__init__(f"Repack bloqueado: {report['blocking_count']} problema(s).\n{details}")


def validation_summary(rows, names, *, compatibility_mode="strict", allow_unknown=False):
    if compatibility_mode not in ("strict", "experimental"):
        raise ValueError("Modo de compatibilidade desconhecido")
    names = set(names)
    selected = [row for row in rows if row["archive"] in names]
    errors, warnings = [], []
    for row in selected:
        def issue(reason, category):
            return dict(archive=row["archive"], path=row["path"], reason=reason, category=category)
        state = row["state"]
        if state == "ausente":
            errors.append(issue("Arquivo extraído ausente. Remoção/renomeação de entradas ainda não é suportada; restaure o caminho original.", "container"))
        elif state == "novo":
            errors.append(issue("Arquivo fora do índice ou sem registro. Adicionar/renomear entradas ainda não é suportado; mantenha arquivos auxiliares fora deste GPK no workspace.", "container"))
        elif state == "não verificado":
            errors.append(issue("Arquivo ainda não verificado", "container"))
        elif state == "inválido":
            target = warnings if compatibility_mode == "experimental" else errors
            for reason in row.get("errors") or ["Formato incompatível"]:
                target.append(issue(reason, "asset_format"))
        if state in ("modificado", "inválido") and row["format"] not in RULES:
            target = warnings if allow_unknown or compatibility_mode == "experimental" else errors
            target.append(issue("Formato desconhecido: conteúdo não validado. Autorize formatos desconhecidos ou use o modo Experimental.", "unknown_format"))
        for warning in row.get("warnings", []):
            warnings.append(issue(warning, "asset_warning"))
    return {
        "operation": "asset_validation", "status": "FAIL" if errors else ("WARN" if warnings else "PASS"),
        "compatibility_mode": compatibility_mode, "allow_unknown": allow_unknown,
        "can_repack": not errors, "archives": sorted(names), "checked": len(selected),
        "modified": sum(row["state"] in ("modificado", "inválido") for row in selected),
        "invalid": sum(row["state"] == "inválido" for row in selected),
        "not_extracted": sum(row["state"] == "não extraído" for row in selected),
        "blocking_count": len(errors), "warning_count": len(warnings),
        "errors": errors, "warnings": warnings,
        "files": [dict(row) for row in selected if row["state"] not in ("original", "não extraído")],
    }


@dataclass(frozen=True)
class Settings:
    game: Path
    packs: Path
    workspace: Path
    reports: Path
    output: Path

    def validate(self):
        if not self.game.is_dir() or not self.packs.is_dir():
            raise ValueError("Selecione uma instalação compatível e uma pasta Packs existentes")
        writable = [self.workspace.resolve(), self.reports.resolve(), self.output.resolve()]
        packs = self.packs.resolve()
        for path in writable:
            if path == packs or packs in path.parents or path in packs.parents:
                raise ValueError("Workspace, relatórios e saída devem ficar separados de Packs")
        for index, path in enumerate(writable):
            for other in writable[index + 1:]:
                if path == other or path in other.parents or other in path.parents:
                    raise ValueError("Workspace, relatórios e saída não podem se sobrepor")


class DesktopService:
    def __init__(self, settings: Settings, key: bytes | None = None):
        settings.validate()
        self.settings = settings
        self.key = key
        self.archives = {}
        self.indexes = {}
        self.index_stamps = {}
        self.rows = []

    @staticmethod
    def reference_stamp(path):
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino

    def current_reference(self, name, *, cancel):
        """Invalidate cached offsets whenever the reference on disk changes."""
        cancel.check()
        archive = self.archives[name]
        stamp = self.reference_stamp(archive)
        if self.index_stamps.get(name) != stamp:
            report = read_stack_index(archive, self.key)
            if self.reference_stamp(archive) != stamp:
                raise ValueError(f"O GPK mudou durante a leitura: {archive}. Aguarde a cópia terminar e tente novamente.")
            self.indexes[name] = report
            self.index_stamps[name] = stamp
        return self.indexes[name]

    def detect(self, *, cancel, progress):
        progress(0, 1, "Localizando CIPHERCODE/PIDX; fallback por GPK ativado…")
        if self.key is None:
            result = find_ciphercode(self.settings.game)
            if result["found"]:
                self.key = bytes.fromhex(result["key_hex"])
            else:
                progress(0, 1, "CIPHERCODE não encontrado; autodetectando a chave em cada GPK…")
        archives = sorted((p for p in self.settings.packs.iterdir() if p.is_file() and p.suffix.lower() == ".gpk"), key=lambda p: p.name.lower())
        if not archives:
            raise ValueError("Nenhum GPK encontrado em Packs")
        found, indexes, stamps = {}, {}, {}
        for number, archive in enumerate(archives, 1):
            cancel.check()
            if archive.stem.casefold() in {n.casefold() for n in found}:
                raise ValueError("Nomes de GPK duplicados")
            found[archive.stem] = archive
            progress(number - 1, len(archives), f"Lendo índice: {archive.name}")
            stamp = self.reference_stamp(archive)
            indexes[archive.stem] = read_stack_index(archive, self.key)
            if self.reference_stamp(archive) != stamp:
                raise ValueError(f"O GPK mudou durante a leitura: {archive}")
            stamps[archive.stem] = stamp
            progress(number, len(archives), archive.name)
        self.archives, self.indexes = found, indexes
        self.index_stamps = stamps
        return self.catalog(cancel=cancel, progress=progress)

    def catalog(self, *, cancel, progress):
        """Open indexes/metadata without hashing or walking the extracted assets."""
        rows = []
        total = sum(len(report["entries"]) for report in self.indexes.values())
        for name, report in self.indexes.items():
            cancel.check()
            report = self.current_reference(name, cancel=cancel)
            progress(len(rows), total, f"Carregando catálogo: {name}")
            metadata = load_metadata(self.settings.workspace / name)
            if metadata:
                check_reference(metadata, report)
            recorded = {e["path"]: e for e in metadata["entries"]} if metadata else {}
            for entry in report["entries"]:
                cancel.check()
                path = Path(entry["path"])
                extracted = recorded.get(entry["path"], {"extracted": False}).get("extracted", True)
                rows.append(dict(archive=name, path=entry["path"], format=_format_name(path),
                                 extension=path.suffix.lower(), size=entry["unpacked_size"] or entry["stored_size"],
                                 state="não verificado" if extracted else "não extraído", errors=[], warnings=[]))
        progress(total, total, "Catálogo pronto; use Atualizar / validar para conferir as edições")
        self.rows = rows
        return rows

    def file_path(self, archive, path):
        if archive not in self.archives:
            raise ValueError("GPK desconhecido")
        return safe_member_path(self.settings.workspace / archive, path)

    def refresh(self, *, cancel, progress, names=None):
        selected_names = set(self.indexes) if names is None else set(names)
        if selected_names - self.indexes.keys():
            raise ValueError("GPK desconhecido na seleção de validação")
        rows = []
        total = sum(len(i["entries"]) for name, i in self.indexes.items() if name in selected_names)
        for name, report in self.indexes.items():
            if name not in selected_names:
                continue
            report = self.current_reference(name, cancel=cancel)
            directory = self.settings.workspace / name
            metadata = load_metadata(directory)
            if metadata:
                check_reference(metadata, report)
            extracted = {e["path"]: e for e in metadata["entries"]} if metadata else {}
            known = set()
            for entry in report["entries"]:
                cancel.check()
                path = self.file_path(name, entry["path"])
                known.add(path)
                record = extracted.get(entry["path"], {"extracted": False})
                row = dict(archive=name, path=entry["path"], format=_format_name(path),
                           extension=path.suffix.lower(), size=entry["unpacked_size"] or entry["stored_size"],
                           state="não extraído", errors=[], warnings=[])
                if record.get("extracted", True):
                    if not path.is_file():
                        row["state"] = "ausente"
                    else:
                        row["size"] = path.stat().st_size
                        progress(len(rows), total, f"Verificando: {name}/{entry['path']}")
                        row["sha256"] = sha256_file(path, cancel=cancel)
                        row["state"] = "original" if row["sha256"] == record.get("extracted_sha256") else "modificado"
                        if row["state"] == "modificado":
                            details = self.inspect(name, entry["path"], cancel=cancel)
                            row.update(errors=details["errors"], warnings=details["warnings"])
                            if row["errors"]:
                                row["state"] = "inválido"
                elif path.exists():
                    row.update(state="novo", errors=["Arquivo presente sem registro de extração; restaure antes de editar"])
                rows.append(row)
                if len(rows) % 100 == 0:
                    progress(len(rows), total, f"{name}/{entry['path']}")
            if directory.is_dir():
                for path in directory.rglob("*"):
                    cancel.check()
                    if path.is_file() and ".sdhq" not in path.relative_to(directory).parts and path.resolve() not in known:
                        rows.append(dict(archive=name, path=path.relative_to(directory).as_posix(),
                                         format=_format_name(path), extension=path.suffix.lower(), size=path.stat().st_size,
                                         state="novo", errors=["Novas entradas GPK não são suportadas"], warnings=[]))
        by_archive = {name: [] for name in self.indexes}
        for row in self.rows:
            if row["archive"] not in selected_names:
                by_archive[row["archive"]].append(row)
        for row in rows:
            by_archive[row["archive"]].append(row)
        self.rows = [row for group in by_archive.values() for row in group]
        return self.rows

    def inspect(self, name, relative, *, cancel):
        report = self.current_reference(name, cancel=cancel)
        metadata = load_metadata(self.settings.workspace / name)
        if metadata:
            check_reference(metadata, report)
        entry = next((e for e in report["entries"] if e["path"] == relative), None)
        if entry is None:
            return {"errors": ["Nova entrada não suportada"], "warnings": []}
        cancel.check()
        kind = _format_name(Path(relative))
        result = dict(archive=name, path=relative, format=kind, rules=RULES.get(kind, "Formato desconhecido: preservar assinatura e tamanho; compatibilidade não verificada."), errors=[], warnings=[])
        # Read only the selected original into an isolated temporary directory.
        with tempfile.TemporaryDirectory(prefix="sdhq-inspect-") as temporary:
            directory = Path(temporary) / "original"
            GPKReader(self.archives[name], self.key).extract(directory, index_report=dict(report, entries=[entry], entry_count=1), cancel=cancel)
            original = safe_member_path(directory, relative)
            try:
                result["original"] = _inspect_asset(original, kind, full_validation=True)
                current = self.file_path(name, relative)
                if current.is_file():
                    result["current"] = _inspect_asset(current, kind, full_validation=True)
                    errors, warnings = _compare_properties(kind, result["original"], result["current"])
                    result["errors"].extend(errors)
                    result["warnings"].extend(warnings)
                if kind not in RULES:
                    result["warnings"].append("Formato desconhecido; requer autorização explícita ao gerar pacote/repack")
            except (OSError, ValueError, UnicodeError) as exc:
                result["errors"].append(str(exc))
        return result

    def extract(self, selection, *, cancel, progress, restore=False):
        results = []
        for name, paths in selection.items():
            cancel.check()
            progress(0, 1, f"Preparando extração: {name}.gpk")
            self.current_reference(name, cancel=cancel)
            before = load_metadata(self.settings.workspace / name)
            previous = {e["path"]: e.get("extracted", True) for e in before["entries"]} if before else {}
            result = extract_selection(self.archives[name], self.settings.workspace / name, self.key, paths,
                                       restore=restore, cancel=cancel, progress=progress)
            requested = set(paths) if paths is not None else {e["path"] for e in result["entries"]}
            newly = {path for path in requested if not previous.get(path, False)}
            changed = requested if restore else newly
            records = {e["path"]: e for e in result["entries"] if e["path"] in changed}
            for row in self.rows:
                if row["archive"] == name and row["path"] in records:
                    entry = records[row["path"]]
                    row.update(state="original", sha256=entry["extracted_sha256"],
                               size=entry["extracted_size"], errors=[], warnings=[])
            results.append({"archive": name, "complete": result["extraction_complete"],
                            "extracted": sum(e.get("extracted", True) for e in result["entries"]),
                            "selected": len(requested), "newly_extracted": 0 if restore else len(newly),
                            "already_extracted": 0 if restore else len(requested - newly),
                            "restored": len(requested) if restore else 0,
                            "destination": str(self.settings.workspace / name)})
        return results

    def validate(self, *, cancel, progress, names=None, compatibility_mode="strict", allow_unknown=False):
        names = list(self.indexes) if names is None else list(names)
        rows = self.refresh(cancel=cancel, progress=progress, names=names)
        return validation_summary(rows, names, compatibility_mode=compatibility_mode, allow_unknown=allow_unknown)

    def preflight(self, names, *, cancel, progress, allow_unknown=False, compatibility_mode="strict"):
        self.last_validation = self.validate(names=names, cancel=cancel, progress=progress,
                                             compatibility_mode=compatibility_mode, allow_unknown=allow_unknown)
        if not self.last_validation["can_repack"]:
            raise ValidationBlocked(self.last_validation)
        return self.rows

    def repack(self, selection, *, cancel, progress, allow_unknown=False, compatibility_mode="strict"):
        snapshot = self.preflight(selection, cancel=cancel, progress=progress, allow_unknown=allow_unknown,
                                  compatibility_mode=compatibility_mode)
        validation = self.last_validation
        output_directory = self.settings.output
        if any((output_directory / f"{name}.gpk").exists() for name in selection):
            output_directory = output_directory / datetime.now().strftime("repack-%Y%m%d-%H%M%S-%f")
        progress(0, len(selection), f"Saída do repack: {output_directory}")
        results = []
        for name in selection:
            cancel.check()
            if load_metadata(self.settings.workspace / name) is None:
                self.extract({name: []}, cancel=cancel, progress=progress)
            output, report = repack_archive(self.settings.workspace / name, self.archives[name], output_directory,
                                            self.key, cancel=cancel, progress=progress,
                                            expected_hashes={row["path"]: row.get("sha256") for row in snapshot if row["archive"] == name})
            report["asset_validation"] = validation
            report["compatibility_mode"] = compatibility_mode
            report["status"] = validation["status"]
            mods.save_mod_report(report, output.with_suffix(output.suffix + ".build.json"))
            results.append(report)
        return results

    def package(self, project, *, cancel, progress, preview=True, expected=None, allow_unknown=False):
        definition = mods._load_project(project)
        names = definition.get("target_archives") or list(self.archives)
        names = {name.casefold() for name in names}
        actual = [name for name in self.archives if name.casefold() in names]
        self.preflight(actual, cancel=cancel, progress=progress, allow_unknown=allow_unknown)
        def callback(*args):
            cancel.check()
            progress(*args)
        return mods.build_mod_package(project, self.settings.workspace, self.settings.output,
                                      preview_only=preview, expected_files=expected, progress=callback)[1]

    def apply_package(self, package, *, cancel, progress):
        inspection = mods.inspect_mod_package(package)
        selection = {}
        mapping = {name.casefold(): name for name in self.archives}
        for item in inspection["files"]:
            name = mapping.get(item["archive"].casefold())
            if name is None:
                raise ValueError(f"GPK necessário não encontrado: {item['archive']}")
            selection.setdefault(name, []).append(item["path"])
        self.extract(selection, cancel=cancel, progress=progress)
        def callback(*args):
            cancel.check()
            progress(*args)
        return mods.apply_mod_package(package, self.settings.workspace, progress=callback)

    def remove_package(self, mod_id, *, cancel, progress):
        def callback(*args):
            cancel.check()
            progress(*args)
        return mods.remove_mod_from_workspace(mod_id, self.settings.workspace, progress=callback)

    def installed_mods(self):
        root = self.settings.workspace / ".sdhq" / "mods"
        return [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*/state.json")]
