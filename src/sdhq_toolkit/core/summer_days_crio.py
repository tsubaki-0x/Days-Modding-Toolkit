"""Summer Days CRio workflow service used by the desktop GUI.

The validated alpha2 CRio backend keeps its technical project and manifest layout.
This adapter presents a modder-friendly workspace under <workspace>/<CRio name>/.
Only the editable TREE is exposed there; headers/manifests stay under .crio.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ..formats.crio import (
    CRioError,
    build_project,
    is_crio,
    load_project,
    parse_container,
    repack_project,
    validate_project,
)
from ..formats.crio.workspace import checked_relative_path, load_json


class SummerDaysCRioService:
    """Reference-based extract/edit/validate/repack flow for one CRio container."""

    def __init__(self, reference, workspace, output, game=None):
        self.reference = Path(reference).expanduser().resolve()
        self.workspace_root = Path(workspace).expanduser().resolve()
        self.output_root = Path(output).expanduser().resolve()
        self.game = Path(game).expanduser().resolve() if game else None
        if not self.reference.is_file():
            raise ValueError(f"CRio de referência não encontrado: {self.reference}")
        if not is_crio(self.reference):
            raise ValueError("O arquivo selecionado não possui a assinatura CRio suportada pela alpha2.")
        self.name = self.reference.name
        self.edit_root = self.workspace_root / self.name
        self.project_root = self.workspace_root / ".crio" / self.name

    def _project(self):
        if not (self.project_root / "_CRIO_PROJECT.json").is_file():
            raise ValueError(
                f"O CRio {self.name} ainda não foi extraído por este workspace. "
                "Use 'Extrair CRio' primeiro."
            )
        project = load_project(self.project_root)
        if project.get("source_kind") != "file" or len(project.get("entries", [])) != 1:
            raise ValueError("Projeto CRio interno inválido para o fluxo de arquivo individual.")
        entry = project["entries"][0]
        if entry.get("kind") != "crio":
            raise ValueError("O projeto interno não aponta para um contêiner CRio.")
        return project, entry

    def _technical_workspace(self):
        project, entry = self._project()
        workspace = self.project_root / checked_relative_path(
            entry["workspace_relative_path"], "workspace path"
        )
        return project, entry, workspace

    def _tree_paths(self):
        project, entry, technical = self._technical_workspace()
        manifest = load_json(technical / "_CRIO" / "manifest.json")
        expected = set()
        for obj in manifest.get("objects", []):
            payload = obj.get("workspace_payload") or ""
            if payload.startswith("TREE/"):
                expected.add(Path(payload).relative_to("TREE").as_posix())
        return project, entry, technical, manifest, expected

    def _visible_files(self):
        if not self.edit_root.is_dir():
            return set()
        return {
            path.relative_to(self.edit_root).as_posix()
            for path in self.edit_root.rglob("*")
            if path.is_file()
        }

    def _sync_visible_tree(self):
        project, entry, technical, manifest, expected = self._tree_paths()
        if not self.edit_root.is_dir():
            raise ValueError(f"Pasta editável não encontrada: {self.edit_root}")
        visible = self._visible_files()
        missing = sorted(expected - visible)
        if missing:
            sample = ", ".join(missing[:5])
            suffix = "…" if len(missing) > 5 else ""
            raise ValueError(
                f"{len(missing)} payload(s) esperado(s) foram removidos do workspace: {sample}{suffix}. "
                "A alpha2 não suporta remover objetos; restaure os arquivos ou extraia novamente."
            )
        extras = sorted(visible - expected)
        tree = technical / "TREE"
        if tree.exists():
            shutil.rmtree(tree)
        shutil.copytree(self.edit_root, tree)
        return extras

    def inspect_reference(self, *, cancel, progress):
        cancel.check()
        progress(0, 1, f"Lendo CRio: {self.name}")
        parsed = parse_container(self.reference, validate_payloads=True)
        cancel.check()
        progress(1, 1, f"{self.name}: {len(parsed.objects)} objetos")
        return {
            "operation": "crio_inspect",
            "files": [],
            "message": (
                f"CRio reconhecido: {self.name} • {len(parsed.objects):,} objetos • "
                f"repack={'sim' if parsed.repack_supported else 'não'}"
            ),
            "reference": str(self.reference),
            "object_count": len(parsed.objects),
            "repack_supported": parsed.repack_supported,
            "limitations": parsed.limitations,
        }

    def extract(self, *, cancel, progress, replace=False):
        cancel.check()
        if self.edit_root.exists() or self.project_root.exists():
            if not replace:
                raise ValueError(
                    f"Já existe um workspace para {self.name}: {self.edit_root}. "
                    "As edições foram preservadas; escolha substituir somente se quiser reextrair o original."
                )
            if self.edit_root.exists():
                shutil.rmtree(self.edit_root)
            if self.project_root.exists():
                shutil.rmtree(self.project_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        progress(0, 3, f"Extraindo {self.name} com o backend CRio alpha2…")
        project = build_project(self.reference, self.project_root)
        cancel.check()
        entry = project["entries"][0]
        technical = self.project_root / checked_relative_path(
            entry["workspace_relative_path"], "workspace path"
        )
        tree = technical / "TREE"
        if not tree.is_dir():
            raise CRioError("A extração não produziu a árvore TREE esperada.")
        progress(1, 3, "Criando workspace editável…")
        shutil.copytree(tree, self.edit_root)
        cancel.check()
        progress(2, 3, "Conferindo workspace visível…")
        visible = self._visible_files()
        progress(3, 3, f"{len(visible):,} payloads editáveis")
        return {
            "operation": "crio_extract",
            "files": [],
            "message": f"Extração concluída: {self.name} → {self.edit_root}",
            "output": str(self.edit_root),
            "workspace": str(self.edit_root),
            "object_count": entry.get("object_count", 0),
            "editable_file_count": len(visible),
            "warnings": [],
        }

    def validate(self, *, cancel, progress):
        cancel.check()
        progress(0, 3, f"Sincronizando alterações de {self.name}…")
        extras = self._sync_visible_tree()
        cancel.check()
        progress(1, 3, "Validando contra o CRio original…")
        report = validate_project(self.project_root, self.reference)
        cancel.check()
        rows = []
        for change in report.get("changes", []):
            internal = change.get("internal_path") or change.get("path") or self.name
            rows.append({"path": internal, "state": "substituir", "warnings": []})
        for extra in extras:
            rows.append({
                "path": extra,
                "state": "novo — não incluído",
                "warnings": ["Novos objetos não são suportados; este arquivo não entra no CRio."],
            })
        progress(3, 3, f"{report['changed_items']:,} alteração(ões) válida(s)")
        return {
            "operation": "crio_validation",
            "files": rows,
            "message": (
                f"CRio validado: {report['changed_items']:,} payload(s) modificado(s); "
                f"{len(extras):,} arquivo(s) novo(s) não incluído(s)."
            ),
            "changed": report["changed_items"],
            "extras": extras,
            "warnings": [
                "Arquivos novos são ignorados porque a alpha2 preserva a árvore original."
            ] if extras else [],
            "report": report,
        }

    def repack(self, *, cancel, progress):
        cancel.check()
        progress(0, 4, f"Preparando repack de {self.name}…")
        validation = self.validate(cancel=cancel, progress=lambda *_: None)
        cancel.check()
        self.output_root.mkdir(parents=True, exist_ok=True)
        output = self.output_root / self.name
        if output.resolve() == self.reference:
            raise ValueError("A saída CRio não pode sobrescrever a referência original.")
        progress(2, 4, "Reconstruindo offsets, tamanhos e payloads…")
        report = repack_project(
            self.project_root,
            self.reference,
            output,
            allow_png_dimension_change=False,
            allow_type_change=False,
            overwrite=True,
        )
        cancel.check()
        progress(4, 4, f"CRio gerado: {output.name}")
        return {
            "operation": "crio_repack",
            "files": validation["files"],
            "message": "CRio gerado com referência original preservada",
            "output": str(output),
            "changed": validation["changed"],
            "warnings": validation["warnings"],
            "validation": validation["report"],
            "repack": report,
        }
