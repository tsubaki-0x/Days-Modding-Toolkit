from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from ..formats.gpk.writer import GPKWriter


def repack_archive(
    source_directory: Path,
    reference: Path,
    output_dir: Path,
    key: bytes | None,
    *,
    progress: Callable[[int, int, str, bool], None] | None = None,
    cancel=None,
    expected_hashes=None,
) -> tuple[Path, dict]:
    output = output_dir / f"{source_directory.name}.gpk"
    report = GPKWriter(reference, key).repack(source_directory, output, progress=progress, cancel=cancel, expected_hashes=expected_hashes)
    return output, report
