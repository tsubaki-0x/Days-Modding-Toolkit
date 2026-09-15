from __future__ import annotations

import json
from pathlib import Path

from ..utils.windows_resources import normalize_ciphercode, read_named_resource


def find_ciphercode(game_directory: Path) -> dict:
    game_directory = game_directory.resolve()
    if not game_directory.is_dir():
        raise FileNotFoundError(game_directory)

    candidates = sorted(game_directory.glob("*.exe"), key=lambda path: path.name.lower())
    packs_directory = game_directory / "Packs"
    if packs_directory.is_dir():
        candidates.extend(sorted(packs_directory.glob("*.exe"), key=lambda path: path.name.lower()))

    checked: list[str] = []
    failures: list[dict] = []
    for executable in candidates:
        checked.append(str(executable))
        try:
            resource = read_named_resource(executable, "CIPHERCODE", "CODE")
        except OSError as exc:
            failures.append({"executable": str(executable), "error": str(exc)})
            continue
        if resource:
            key = normalize_ciphercode(resource)
            return {
                "found": True,
                "executable": str(executable),
                "resource_name": "CIPHERCODE",
                "resource_type": "CODE",
                "resource_size": len(resource),
                "key_size": len(key),
                "key_hex": key.hex().upper(),
                "checked_executables": checked,
                "failures": failures,
            }

    return {
        "found": False,
        "checked_executables": checked,
        "failures": failures,
    }


def save_key_report(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
