from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .config import ApiConfig
from .indexer import index_status, read_by_path, reindex, search


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_config(config: ApiConfig) -> CheckResult:
    result = CheckResult()
    vault_path = Path(config.vault_path)
    database_path = Path(config.database_path)
    if not vault_path.exists():
        result.errors.append(f"vault_path does not exist: {vault_path}")
    elif not vault_path.is_dir():
        result.errors.append(f"vault_path is not a directory: {vault_path}")
    parent = database_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".kb-api-write-test-", delete=True):
            pass
    except OSError as exc:
        result.errors.append(f"database parent is not writable: {parent} ({exc})")
    if not os.environ.get(config.token_env):
        result.warnings.append(f"token env var is not set: {config.token_env}")
    if not os.environ.get(config.admin_token_env):
        result.warnings.append(f"admin token env var is not set: {config.admin_token_env}")
    if config.host != "127.0.0.1":
        result.warnings.append(f"server host is {config.host}; default local-only host is 127.0.0.1")
    return result


def status_lines(config: ApiConfig) -> list[str]:
    status = index_status(config)
    return [
        f"vault_path: {Path(config.vault_path)} exists={Path(config.vault_path).exists()}",
        f"database_path: {Path(config.database_path)} exists={status.database_exists}",
        f"notes: {status.notes}",
        f"chunks: {status.chunks}",
        f"newest_received: {status.newest_received or '(none)'}",
        f"token_env: {config.token_env} set={bool(os.environ.get(config.token_env))}",
        f"admin_token_env: {config.admin_token_env} set={bool(os.environ.get(config.admin_token_env))}",
    ]


def doctor_lines(config: ApiConfig) -> tuple[list[str], bool]:
    lines = ["doctor: kb_api"]
    check = validate_config(config)
    if check.errors:
        lines.append("validate-config: failed")
        lines.extend(f"ERROR: {item}" for item in check.errors)
    else:
        lines.append("validate-config: ok")
    lines.extend(f"WARNING: {item}" for item in check.warnings)
    lines.append("status:")
    lines.extend(f"  {line}" for line in status_lines(config))
    status = index_status(config)
    lines.append("next:")
    if check.errors:
        lines.append("  Fix config errors, then rerun: python3 -m kb_api doctor --config <config>")
    elif not status.database_exists:
        lines.append("  Run: python3 -m kb_api reindex --config <config>")
    elif not os.environ.get(config.token_env):
        lines.append(f"  Set token env var before serving: export {config.token_env}=<token>")
    else:
        lines.append("  Start API: python3 -m kb_api serve --config <config>")
        lines.append("  Verify: curl -sS http://127.0.0.1:8765/health")
    return lines, check.ok


def smoke_test(config: ApiConfig) -> list[str]:
    lines = [
        f"python: {platform.python_version()}",
        f"config vault_path: {Path(config.vault_path)}",
        f"config database_path: {Path(config.database_path)}",
    ]
    check = validate_config(config)
    if check.errors:
        lines.append("validate-config: failed")
        lines.extend(f"ERROR: {item}" for item in check.errors)
        raise RuntimeError("\n".join(lines))
    lines.append("validate-config: ok")
    stats = reindex(config)
    lines.append(f"reindex: ok notes={stats.notes} chunks={stats.chunks}")
    results = search(config, "SSO", limit=1)
    if not results:
        raise RuntimeError("\n".join(lines + ["search: failed no result for sample query SSO"]))
    first = results[0]
    lines.append(f"search: ok query=SSO source={first['path']}")
    note = read_by_path(config, first["path"])
    lines.append(f"read: ok title={note['title']}")
    context_results = search(config, "GitHub", limit=3)
    lines.append(f"context: ok evidence={len(context_results)}")
    return lines
