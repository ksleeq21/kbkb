from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ImportState:
    imported: dict[str, dict[str, str]] = field(default_factory=dict)

    def mark_imported(self, message_key: str, path: str) -> None:
        self.imported[message_key] = {
            "path": path,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> ImportState:
        if not self.path.exists():
            return ImportState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"State file is not valid JSON: {self.path}") from exc
        imported = data.get("imported")
        if not isinstance(imported, dict):
            raise ValueError(f"State file missing imported object: {self.path}")
        return ImportState(imported={str(k): dict(v) for k, v in imported.items()})

    def save(self, state: ImportState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"imported": state.imported}, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
