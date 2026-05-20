from __future__ import annotations

from pathlib import Path


def render_linux_config_template(home: str | Path | None = None) -> str:
    home_path = Path(home).expanduser() if home is not None else Path.home()
    home_text = home_path.as_posix()
    return f"""vault_path: "{home_text}/kb/KnowledgeVault-Enriched"
raw_vault_path: "{home_text}/kb/KnowledgeVault-Raw"
enriched_vault_path: "{home_text}/kb/KnowledgeVault-Enriched"
enrichment_cache_path: "{home_text}/.local/share/kb-api/enrichment-cache"
attachment_policy: "copy"
database_path: "{home_text}/.local/share/kb-api/kb.sqlite"
token_env: "KB_API_TOKEN"
admin_token_env: "KB_API_ADMIN_TOKEN"
ignore_dirs:
  - ".obsidian"
  - ".trash"
  - ".git"
server:
  host: "127.0.0.1"
  port: 8765
"""


LINUX_CONFIG_TEMPLATE = render_linux_config_template()
