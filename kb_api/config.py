from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kb_win_sync.simple_yaml import load_simple_yaml


@dataclass(frozen=True)
class ApiConfig:
    vault_path: Path
    database_path: Path
    host: str = "127.0.0.1"
    port: int = 8765
    token_env: str = "KB_API_TOKEN"
    admin_token_env: str = "KB_API_ADMIN_TOKEN"
    ignore_dirs: list[str] = field(default_factory=lambda: [".obsidian", ".trash", ".git"])


def load_config(path: str | Path) -> ApiConfig:
    data = load_simple_yaml(Path(path).read_text(encoding="utf-8"))
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> ApiConfig:
    missing = [key for key in ["vault_path", "database_path"] if key not in data]
    if missing:
        raise ValueError(f"Missing required API config keys: {', '.join(missing)}")
    server = data.get("server") or {}
    if server and not isinstance(server, dict):
        raise ValueError("server must be an object with host and port")
    return ApiConfig(
        vault_path=Path(str(data["vault_path"])),
        database_path=Path(str(data["database_path"])),
        host=str(server.get("host", "127.0.0.1")),
        port=int(server.get("port", 8765)),
        token_env=str(data.get("token_env", "KB_API_TOKEN")),
        admin_token_env=str(data.get("admin_token_env", "KB_API_ADMIN_TOKEN")),
        ignore_dirs=[str(item) for item in data.get("ignore_dirs", [".obsidian", ".trash", ".git"])],
    )
