from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .config import SyncConfig


@dataclass(frozen=True)
class SyncPlan:
    files: list[Path]


def build_full_sync_plan(vault_path: Path) -> SyncPlan:
    ignored_parts = {".obsidian", ".trash", ".git"}
    files = [
        path for path in vault_path.rglob("*")
        if path.is_file() and not (set(path.relative_to(vault_path).parts) & ignored_parts)
    ]
    return SyncPlan(files=files)


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict[str, str]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


class SftpSyncer:
    def __init__(self, config: SyncConfig):
        self.config = config

    def sync(self, vault_path: Path) -> int:
        if not self.config.enabled:
            return 0
        try:
            import paramiko  # type: ignore
        except ImportError as exc:
            raise RuntimeError("paramiko is required for SFTP sync") from exc
        key = paramiko.RSAKey.from_private_key_file(self.config.key_path) if self.config.key_path else None
        transport = paramiko.Transport((self.config.host, self.config.port))
        transport.connect(username=self.config.username, pkey=key)
        uploaded = 0
        try:
            sftp = paramiko.SFTPClient.from_transport(transport)
            for local in build_full_sync_plan(vault_path).files:
                rel = local.relative_to(vault_path).as_posix()
                remote = f"{self.config.remote_path.rstrip('/')}/{rel}"
                _mkdirs(sftp, str(Path(remote).parent).replace("\\", "/"))
                sftp.put(str(local), remote)
                uploaded += 1
        finally:
            transport.close()
        return uploaded


def _mkdirs(sftp, remote_dir: str) -> None:
    current = ""
    for part in [p for p in remote_dir.split("/") if p]:
        current += "/" + part
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)
