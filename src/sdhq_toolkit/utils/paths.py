from __future__ import annotations

from pathlib import Path, PurePosixPath


def safe_member_path(root: Path, member: str) -> Path:
    """Resolve an archive member without allowing traversal outside root."""
    normalized = PurePosixPath(member.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Unsafe archive path: {member}")
    candidate = (root / Path(*normalized.parts)).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(f"Unsafe archive path: {member}")
    return candidate

