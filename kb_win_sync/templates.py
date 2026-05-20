from __future__ import annotations

import os
from pathlib import Path


def _windows_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()).expanduser()


def render_windows_config_template(home: str | Path | None = None) -> str:
    home_path = Path(home).expanduser() if home is not None else _windows_home()
    home_text = home_path.as_posix()
    vault_path = f"{home_text}/KnowledgeVault"
    return f"""vault_path: "{vault_path}"
state_path: "{home_text}/AppData/Local/kb-win-sync/state/import-state.json"
log_path: "{home_text}/AppData/Local/kb-win-sync/logs/kb-win-sync.log"
outlook:
  folders:
sync:
  enabled: false
  host: "linux-dev.example.internal"
  port: 22
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "{home_text}/.ssh/id_ed25519"
  manifest_path: "{vault_path}/.kb-sync-manifest.json"
"""


WINDOWS_CONFIG_TEMPLATE = render_windows_config_template()
