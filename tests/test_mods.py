from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from sdhq_toolkit.core.asset_validation import create_asset_baseline
from sdhq_toolkit.core.mods import (
    apply_mod_package,
    build_mod_package,
    create_mod_project,
    inspect_mod_package,
    remove_mod_from_workspace,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_workspace(root: Path, files: dict[str, bytes]) -> Path:
    workspace = root / "workspace"
    archive = workspace / "System"
    entries = []
    for relative, data in files.items():
        path = archive / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append(
            {
                "path": relative,
                "extracted_size": len(data),
                "extracted_sha256": _sha256(data),
            }
        )
    metadata = {
        "format": "GPK/STACK",
        "source_archive": "C:\\Games\\School Days HQ\\Packs\\System.GPK",
        "archive_size": 123456,
        "entry_count": len(entries),
        "entries": entries,
    }
    marker = archive / ".sdhq" / "archive.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(metadata), encoding="utf-8")
    return workspace


class ModPackageTests(unittest.TestCase):
    def _build_package(self, root: Path) -> tuple[Path, bytes, bytes]:
        original = b"logo_enabled=1\n"
        modified = b"logo_enabled=0\n"
        workspace = _make_workspace(
            root / "creator",
            {"INI/STARTSCRIPT.INI": original, "TITLE/README.TXT": b"unchanged\n"},
        )
        baseline = root / "asset_baseline.json"
        clean_report = create_asset_baseline(workspace, baseline)
        self.assertEqual(clean_report["status"], "PASS")
        (workspace / "System" / "INI" / "STARTSCRIPT.INI").write_bytes(modified)
        project = root / "project"
        create_mod_project(
            project,
            mod_id="example.no-logo",
            name="No Logo",
            author="Toolkit Test",
            version="1.0.0",
            description="Controlled test mod",
            target_archives=["System"],
        )
        package, report = build_mod_package(
            project,
            workspace,
            root / "dist",
            asset_baseline=baseline,
        )
        self.assertEqual(report["file_count"], 1)
        self.assertEqual(report["asset_preflight"]["status"], "PASS")
        return package, original, modified

    def test_build_inspect_apply_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, original, modified = self._build_package(root)
            inspection = inspect_mod_package(package)
            self.assertEqual(inspection["status"], "PASS")
            self.assertEqual(inspection["archives"], ["System"])
            self.assertEqual(inspection["file_count"], 1)
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"mod.json", "files/System/INI/STARTSCRIPT.INI"},
                )

            clean_workspace = _make_workspace(
                root / "consumer",
                {"INI/STARTSCRIPT.INI": original, "TITLE/README.TXT": b"unchanged\n"},
            )
            state = apply_mod_package(package, clean_workspace)
            target = clean_workspace / "System" / "INI" / "STARTSCRIPT.INI"
            self.assertEqual(state["status"], "PASS")
            self.assertEqual(target.read_bytes(), modified)
            self.assertEqual(
                apply_mod_package(package, clean_workspace)["status"],
                "ALREADY_APPLIED",
            )

            removed = remove_mod_from_workspace("example.no-logo", clean_workspace)
            self.assertEqual(removed["status"], "PASS")
            self.assertEqual(removed["restored_files"], 1)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(
                remove_mod_from_workspace("example.no-logo", clean_workspace)["status"],
                "NOT_INSTALLED",
            )

    def test_apply_rejects_a_dirty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, original, _ = self._build_package(root)
            workspace = _make_workspace(root / "consumer", {"INI/STARTSCRIPT.INI": original})
            (workspace / "System" / "INI" / "STARTSCRIPT.INI").write_bytes(b"other mod\n")
            with self.assertRaisesRegex(ValueError, "Mod conflict"):
                apply_mod_package(package, workspace)

    def test_inspection_rejects_tampered_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, _, _ = self._build_package(root)
            tampered = root / "tampered.sdmod"
            with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(tampered, "w") as target:
                for info in source.infolist():
                    data = source.read(info)
                    if info.filename.startswith("files/"):
                        data = b"tampered\n"
                    target.writestr(info.filename, data)
            with self.assertRaisesRegex(ValueError, "mismatch"):
                inspect_mod_package(tampered)

    def test_build_rejects_new_archive_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = _make_workspace(root, {"INI/STARTSCRIPT.INI": b"clean\n"})
            extra = workspace / "System" / "NEW.BIN"
            extra.write_bytes(b"not declared")
            project = root / "project"
            create_mod_project(
                project,
                mod_id="example.new-file",
                name="Unsupported New File",
                author="Toolkit Test",
                version="1.0.0",
                target_archives=["System"],
            )
            with self.assertRaisesRegex(ValueError, "New GPK entries"):
                build_mod_package(project, workspace, root / "dist")


if __name__ == "__main__":
    unittest.main()
