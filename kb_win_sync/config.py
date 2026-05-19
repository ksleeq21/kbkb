from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .simple_yaml import load_simple_yaml


@dataclass(frozen=True)
class OutlookFolderConfig:
    name: str
    outlook_path: str
    target_folder: str
    tags: list[str] = field(default_factory=list)
    save_msg: bool = False
    save_attachments: bool = True


@dataclass(frozen=True)
class SyncConfig:
    enabled: bool = False
    host: str = ""
    port: int = 22
    username: str = ""
    remote_path: str = ""
    key_path: str = ""


@dataclass(frozen=True)
class WinConfig:
    vault_path: Path
    state_path: Path
    log_path: Path
    folders: list[OutlookFolderConfig]
    sync: SyncConfig = field(default_factory=SyncConfig)


def load_config(path: str | Path) -> WinConfig:
    data = load_simple_yaml(Path(path).read_text(encoding="utf-8"))
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> WinConfig:
    required = ["vault_path", "state_path", "log_path", "outlook"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Missing required Windows config keys: {', '.join(missing)}")
    outlook = data.get("outlook") or {}
    raw_folders = outlook.get("folders") or []
    if not raw_folders:
        raise ValueError("At least one outlook.folders entry is required")
    folder_errors: list[str] = []
    folders: list[OutlookFolderConfig] = []
    for index, item in enumerate(raw_folders, start=1):
        missing_folder_keys = [key for key in ["name", "outlook_path", "target_folder"] if key not in item]
        if missing_folder_keys:
            folder_errors.append(f"outlook.folders[{index}] missing: {', '.join(missing_folder_keys)}")
            continue
        folders.append(
            OutlookFolderConfig(
                name=str(item["name"]),
                outlook_path=str(item["outlook_path"]),
                target_folder=str(item["target_folder"]).strip("/\\"),
                tags=[str(tag) for tag in item.get("tags", [])],
                save_msg=bool(item.get("save_msg", False)),
                save_attachments=bool(item.get("save_attachments", True)),
            )
        )
    if folder_errors:
        raise ValueError("; ".join(folder_errors))
    sync_data = data.get("sync") or {}
    sync = SyncConfig(
        enabled=bool(sync_data.get("enabled", False)),
        host=str(sync_data.get("host", "")),
        port=int(sync_data.get("port", 22)),
        username=str(sync_data.get("username", "")),
        remote_path=str(sync_data.get("remote_path", "")),
        key_path=str(sync_data.get("key_path", "")),
    )
    return WinConfig(
        vault_path=Path(str(data["vault_path"])),
        state_path=Path(str(data["state_path"])),
        log_path=Path(str(data["log_path"])),
        folders=folders,
        sync=sync,
    )
