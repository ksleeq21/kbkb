from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .config import SyncConfig
from .text import safe_text


@dataclass(frozen=True)
class SyncPlan:
    files: list[Path]


def build_full_sync_plan(vault_path: Path) -> SyncPlan:
    ignored_parts = {".obsidian", ".trash", ".git"}
    ignored_names = {".kb-sync-manifest.json", ".kb-sync-manifest.json.tmp"}
    files = [
        path for path in vault_path.rglob("*")
        if path.is_file() and path.name not in ignored_names and not (set(path.relative_to(vault_path).parts) & ignored_parts)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def build_incremental_sync_plan(vault_path: Path, manifest: dict[str, str]) -> tuple[SyncPlan, dict[str, str]]:
    next_manifest: dict[str, str] = {}
    changed: list[Path] = []
    for local in build_full_sync_plan(vault_path).files:
        rel = local.relative_to(vault_path).as_posix()
        digest = file_digest(local)
        next_manifest[rel] = digest
        if manifest.get(rel) != digest:
            changed.append(local)
    return SyncPlan(files=changed), next_manifest


class SftpSyncer:
    def __init__(self, config: SyncConfig):
        self.config = config

    def sync(self, vault_path: Path) -> int:
        if not self.config.enabled:
            return 0
        manifest_path = self.config.manifest_path or (vault_path / ".kb-sync-manifest.json")
        previous_manifest = load_manifest(manifest_path)
        plan, next_manifest = build_incremental_sync_plan(vault_path, previous_manifest)
        try:
            import paramiko  # type: ignore
        except ImportError as exc:
            raise RuntimeError("paramiko is required for SFTP sync") from exc
        key = _load_private_key(paramiko, self.config.key_path) if self.config.key_path else None
        transport = paramiko.Transport((self.config.host, self.config.port))
        transport.connect(username=self.config.username, pkey=key)
        uploaded = 0
        try:
            sftp = paramiko.SFTPClient.from_transport(transport)
            for local in plan.files:
                rel = local.relative_to(vault_path).as_posix()
                remote = f"{self.config.remote_path.rstrip('/')}/{rel}"
                try:
                    _mkdirs(sftp, str(Path(remote).parent).replace("\\", "/"))
                    sftp.put(str(local), remote)
                    uploaded += 1
                    previous_manifest[rel] = next_manifest[rel]
                except Exception as exc:
                    logging.error(
                        "SKIPPED_SYNC_UPLOAD action=skip rel=%s local=%s remote=%s error_type=%s error=%s",
                        safe_text(rel, limit=500),
                        safe_text(local, limit=500),
                        safe_text(remote, limit=500),
                        type(exc).__name__,
                        safe_text(exc, limit=500),
                    )
        finally:
            transport.close()
        save_manifest(manifest_path, {rel: digest for rel, digest in next_manifest.items() if previous_manifest.get(rel) == digest})
        return uploaded


def _mkdirs(sftp, remote_dir: str) -> None:
    current = ""
    for part in [p for p in remote_dir.split("/") if p]:
        current += "/" + part
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def _load_private_key(paramiko, key_path: str):
    errors: list[str] = []
    for key_cls_name in ["RSAKey", "Ed25519Key", "ECDSAKey", "DSSKey"]:
        key_cls = getattr(paramiko, key_cls_name, None)
        if key_cls is None:
            continue
        try:
            return key_cls.from_private_key_file(key_path)
        except Exception as exc:
            errors.append(f"{key_cls_name}: {exc}")
    raise RuntimeError(f"Could not load SSH private key: {key_path}; " + "; ".join(errors))
