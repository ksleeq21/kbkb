from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import WinConfig
from .state import StateStore


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_config(config: WinConfig) -> CheckResult:
    result = CheckResult()
    if not config.folders:
        result.warnings.append("outlook.folders is empty; run list-mailboxes to select folders before import")
    for folder in config.folders:
        if not folder.name.strip():
            result.errors.append("folder name must not be empty")
        if not folder.outlook_path.strip():
            result.errors.append(f"folder {folder.name}: outlook_path must not be empty")
        if not folder.target_folder.strip():
            result.errors.append(f"folder {folder.name}: target_folder must not be empty")
    if config.vault_path.exists() and not config.vault_path.is_dir():
        result.errors.append(f"vault_path exists but is not a directory: {config.vault_path}")
    if not config.vault_path.exists():
        result.warnings.append(f"vault_path does not exist yet: {config.vault_path}")
    for label, path in {"state_path parent": config.state_path.parent, "log_path parent": config.log_path.parent}.items():
        if not Path(path).exists():
            result.warnings.append(f"{label} does not exist yet: {path}")
    if config.sync.enabled:
        if not config.sync.host:
            result.errors.append("sync.enabled is true but sync.host is empty")
        if not config.sync.username:
            result.errors.append("sync.enabled is true but sync.username is empty")
        if not config.sync.remote_path:
            result.errors.append("sync.enabled is true but sync.remote_path is empty")
    return result


def status_lines(config: WinConfig) -> list[str]:
    state_exists = config.state_path.exists()
    imported_count = 0
    last_import = "(none)"
    state_error = ""
    if state_exists:
        try:
            state = StateStore(config.state_path).load()
            imported_count = len(state.imported)
            imported_times = [item.get("imported_at", "") for item in state.imported.values()]
            last_import = max(imported_times) if imported_times else "(none)"
        except ValueError as exc:
            state_error = str(exc)
    lines = [
        f"vault_path: {config.vault_path} exists={config.vault_path.exists()}",
        f"state_path: {config.state_path} exists={state_exists}",
        f"configured_folders: {len(config.folders)}",
        f"imported_count: {imported_count}",
        f"last_import: {last_import}",
        f"sync_enabled: {config.sync.enabled}",
    ]
    if state_error:
        lines.append(f"state_error: {state_error}")
    return lines


def doctor_lines(config: WinConfig) -> tuple[list[str], bool]:
    lines = ["doctor: kb_win_sync"]
    check = validate_config(config)
    if check.errors:
        lines.append("validate-config: failed")
        lines.extend(f"ERROR: {item}" for item in check.errors)
    else:
        lines.append("validate-config: ok")
    lines.extend(f"WARNING: {item}" for item in check.warnings)
    lines.append("status:")
    lines.extend(f"  {line}" for line in status_lines(config))
    lines.append("next:")
    if check.errors:
        lines.append("  Fix config errors, then rerun: python -m kb_win_sync doctor --config <config>")
    elif not config.folders:
        lines.append("  Select Outlook folders: python -m kb_win_sync list-mailboxes --config <config>")
        lines.append("  Then preview import: python -m kb_win_sync --config <config> --dry-run")
    else:
        lines.append("  Preview import: python -m kb_win_sync --config <config> --dry-run")
        lines.append("  Run import manually before registering Task Scheduler.")
    return lines, check.ok
