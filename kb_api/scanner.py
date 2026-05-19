from __future__ import annotations

from pathlib import Path


def scan_markdown(vault_path: str | Path, ignore_dirs: list[str] | None = None) -> list[Path]:
    root = Path(vault_path)
    ignored = set(ignore_dirs or [".obsidian", ".trash", ".git"])
    files: list[Path] = []
    for path in root.rglob("*.md"):
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & ignored:
            continue
        files.append(path)
    return sorted(files)
