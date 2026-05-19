# Setup, Tokens, and Uninstall

이 문서는 설치, 토큰 설정, 서비스 등록, 제거 절차를 한 곳에 모은 운영용 가이드다.

설치부터 검색까지의 전체 사용자 흐름은 `docs/END_TO_END_WORKFLOW.md`를 먼저 참고한다.

## Token Policy

이 프로젝트는 GitHub 또는 GitHub Enterprise를 개인 지식 데이터 저장소로 사용하지 않는다. GitHub는 소스 코드 저장소로만 사용할 수 있으며, 다음 데이터는 GitHub에 올리면 안 된다.

- Obsidian vault contents
- imported email Markdown files
- `.msg` originals
- attachments
- SQLite databases
- logs
- local config files
- API tokens
- SSH private keys
- `.env` files

### KB API Tokens

The Linux API uses local bearer tokens:

- `KB_API_TOKEN`: normal read-only API token for `/search`, `/notes/by-path`, and `/context`.
- `KB_API_ADMIN_TOKEN`: admin token for `/admin/reindex`.

Generate strong local tokens on Linux:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Set them for a shell session:

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
```

For user-level systemd, prefer a private environment file outside the repo:

```bash
mkdir -p ~/.config/kb-api
chmod 700 ~/.config/kb-api
printf 'KB_API_TOKEN=%s\nKB_API_ADMIN_TOKEN=%s\n' 'replace-with-generated-token' 'replace-with-different-generated-token' > ~/.config/kb-api/env
chmod 600 ~/.config/kb-api/env
```

Then add this to the service file:

```ini
EnvironmentFile=%h/.config/kb-api/env
```

Do not commit this environment file.

### Cline/Codex Skill Token

The skill scripts read:

```bash
export KB_API_BASE_URL=http://127.0.0.1:8765
export KB_API_TOKEN='replace-with-generated-token'
```

They do not need the admin token.

### SFTP/SSH Key

Windows-to-Linux sync uses SSH/SFTP when enabled. It needs an SSH private key path in local Windows config only:

```yaml
sync:
  enabled: true
  host: "linux-dev.example.internal"
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "C:/Users/you/.ssh/id_rsa"
```

Never commit SSH private keys or local config files.

## Install

Install the source tree in editable mode first. This exposes the shorter
`kb-api` and `kb-win-sync` commands used below.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Windows Outlook importer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
```

If editable install is not available, use the legacy module commands instead:
`python3 -m kb_api` and `python -m kb_win_sync`.

## First-Run Path

Use this order for the first successful setup:

1. Install editable commands and run the synthetic smoke test.
2. Linux: create API config and tokens.
3. Linux: create or verify the enriched vault path, then start the API after reindex.
4. Linux: verify `/health`, `/health?deep=true`, and `/search`.
5. Windows: create Outlook import config.
6. Windows: run `list-mailboxes`, choose mailbox indexes, and copy the generated snippets into config.
7. Windows: validate config and run `--dry-run`.
8. Windows: run import manually once.
9. Windows: enable Task Scheduler only after manual import works.
10. Linux: run Cline CLI enrichment from raw Markdown to enriched Markdown.
11. Linux: reindex the enriched vault.
12. Cline/Codex: run `kb_search.py` against the API.

See `docs/FIRST_RUN_UX_REVIEW.md` for the full usability review and additional improvement candidates.

### Linux API

From the source repository:

```bash
python -m unittest discover -s tests -v
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
kb-api smoke-test --config examples/linux-config.fixture.yaml
```

Create local config outside the repo:

```bash
mkdir -p ~/.config/kb-api ~/.local/share/kb-api
kb-api init-config --output ~/.config/kb-api/config.yaml
```

Edit:

```bash
vim ~/.config/kb-api/config.yaml
```

Validate first:

```bash
kb-api validate-config --config ~/.config/kb-api/config.yaml
kb-api doctor --config ~/.config/kb-api/config.yaml
```

After Windows has synced raw Markdown to Linux, enrich and index:

```bash
kb-api enrich --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
kb-api status --config ~/.config/kb-api/config.yaml
```

Run manually:

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
kb-api serve --config ~/.config/kb-api/config.yaml
```

Verify from another shell:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

### Linux systemd Service

Install user service:

```bash
mkdir -p ~/.config/systemd/user
cp examples/kb-api.service ~/.config/systemd/user/kb-api.service
```

Edit paths and token handling:

```bash
vim ~/.config/systemd/user/kb-api.service
```

Recommended service token pattern:

```ini
EnvironmentFile=%h/.config/kb-api/env
```

The included `examples/kb-api.service` already uses this pattern. You still need to edit `WorkingDirectory` and `ExecStart` paths for your machine.

Start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-api.service
systemctl --user status kb-api.service
```

### Windows Outlook Import

Install optional Windows dependencies:

```powershell
python -m pip install -e ".[windows]"
```

Create local config outside the repo:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\kb-win-sync"
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync list-mailboxes
notepad "$env:USERPROFILE\kb-win-sync\config.yaml"
```

`list-mailboxes` prints Outlook mailboxes and folders with numeric indexes, then asks:

```text
동기화 시키고 싶은 메일함 Index(예: 1,2,3,5):
```

Copy the generated `outlook.folders` snippets into the local config and adjust `name`, `target_folder`, and `tags` as needed.

Validate and preview:

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

Run:

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

### Windows Task Scheduler

For detailed Outlook folder selection and Task Scheduler GUI steps, see `docs/WINDOWS_OUTLOOK_SETUP.md`.

Use `examples/run-kb-win-sync.bat` as the action target after editing the config path inside the script or matching the default path.

Recommended settings:

- Run only when the user is logged on if Outlook COM cannot run in a background session.
- Start in the repository directory or the installed package environment.
- Run daily after Outlook is normally available.
- Capture stdout/stderr through Task Scheduler history or redirect in a local wrapper script outside the repo.

Register the schedule only after manual `--dry-run` and manual import both work.

### SFTP Sync Preflight

Before setting `sync.enabled: true`, verify SSH/SFTP independently from Windows:

```powershell
ssh your-linux-user@linux-dev.example.internal
```

On Linux, verify the remote raw vault directory exists and is writable. Also create the enriched vault directory used by `kb_api`.

```bash
mkdir -p /home/your-linux-user/kb/KnowledgeVault-Raw
mkdir -p /home/your-linux-user/kb/KnowledgeVault-Enriched
test -w /home/your-linux-user/kb/KnowledgeVault-Raw
```

Keep `sync.enabled: false` until SSH, remote path, and permissions are confirmed. Do not use GitHub as a sync backend.

`kb_win_sync` should sync into the raw vault. The Linux Cline CLI enrichment step should read that raw vault and write a separate enriched vault. Configure `kb_api.vault_path` to the enriched vault.

## Upgrade

Pull or copy the new source code, then rerun tests and validation:

```bash
python -m unittest discover -s tests -v
kb-api validate-config --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
systemctl --user restart kb-api.service
```

On Windows, rerun:

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

## Uninstall

### Stop and Remove Linux API Service

```bash
systemctl --user disable --now kb-api.service
rm -f ~/.config/systemd/user/kb-api.service
systemctl --user daemon-reload
```

Remove local API config, tokens, and DB only if you no longer need them:

```bash
rm -rf ~/.config/kb-api
rm -rf ~/.local/share/kb-api
```

Do not delete your Obsidian vault unless you intentionally want to remove your personal knowledge data.

### Remove Windows Scheduled Import

In Task Scheduler:

1. Open Task Scheduler.
2. Find the task that runs `run-kb-win-sync.bat` or `kb-win-sync`.
3. Disable it first.
4. Delete it after confirming no daily import is needed.

Remove local Windows config/state/logs only if no longer needed:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\kb-win-sync"
```

Do not delete the Windows Obsidian vault unless you intentionally want to remove your personal knowledge data.

### Remove Python Package Install

If installed editable from this repository:

```bash
python3 -m pip uninstall kbkb
```

On Windows:

```powershell
python -m pip uninstall kbkb
```

If you only ran modules directly from the source checkout and did not install the package, there may be no Python package to uninstall.

## Verification Checklist

After setup:

- `kb-api smoke-test --config examples/linux-config.fixture.yaml` succeeds with synthetic data.
- `kb-api status --config <linux-config>` shows expected notes/chunks.
- `kb-win-sync validate-config --config <windows-config>` reports no errors.
- No token values are printed in logs or status output.
- No vault data, `.msg`, SQLite DB, `.env`, local config, or SSH key is inside the source repository.

After uninstall:

- `systemctl --user status kb-api.service` no longer shows a running service.
- Task Scheduler no longer runs the Windows import.
- Local config/token files are removed only if intentionally deleted.
- Obsidian vault data remains wherever the user chose to keep it.
