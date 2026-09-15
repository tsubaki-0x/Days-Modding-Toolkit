from __future__ import annotations

from pathlib import Path


def validate_basic_archive(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append("Archive does not exist")
    elif not path.is_file():
        errors.append("Archive path is not a file")
    elif path.stat().st_size == 0:
        errors.append("Archive is empty")
    if path.suffix.lower() != ".gpk":
        errors.append("Expected a .gpk extension")
    return errors

