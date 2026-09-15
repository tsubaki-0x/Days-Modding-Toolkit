from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sdhq_toolkit.cli import main  # noqa: E402


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if not arguments:
        arguments = [
            "inventory",
            "--packs",
            str(ROOT / "samples" / "packs"),
            "--extracted",
            str(ROOT / "samples" / "extracted"),
            "--output",
            str(ROOT / "reports"),
            "--skip-hash",
        ]
    elif arguments[0] != "inventory":
        arguments.insert(0, "inventory")
    raise SystemExit(main(arguments))
