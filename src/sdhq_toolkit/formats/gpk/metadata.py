from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ArchiveMetadata:
    format: str
    source: str
    source_sha256: str
    tool_version: str
    entries: list[dict] = field(default_factory=list)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ArchiveMetadata":
        return cls(**json.loads(path.read_text(encoding="utf-8")))

