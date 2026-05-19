# Setup, Tokens, and Uninstall

이 문서는 설치, 토큰 설정, 서비스 등록, 제거 절차를 한 곳에 모은 운영용 가이드다.

## Token Policy

### GitHub Token

GitHub token is not required.

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

If a GitHub token exists on the machine for other development work, do not put it in this project config. `kb_win_sync`, `kb_api`, and the skill scripts do not read or need `GITHUB_TOKEN`.

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
  remote_path: "/home/your-linux-user/kb/KnowledgeVault"
  key_path: "C:/Users/you/.ssh/id_rsa"
```

Never commit SSH private keys or local config files.

## Install

## First-Run Path

Use this order for the first successful setup:

1. Linux: run the synthetic smoke test.
2. Linux: create API config and tokens.
3. Linux: reindex and start the API.
4. Linux: verify `/health`, `/health?deep=true`, and `/search`.
5. Windows: create Outlook import config.
6. Windows: validate config and run `--dry-run`.
7. Windows: run import manually once.
8. Windows: enable Task Scheduler only after manual import works.
9. Linux: reindex the synced vault.
10. Cline/Codex: run `kb_search.py` against the API.

See `docs/FIRST_RUN_UX_REVIEW.md` for the full usability review and additional improvement candidates.

### Linux API

From the source repository:

```bash
python3 -m unittest discover -s tests -v
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
python3 -m kb_api smoke-test --config examples/linux-config.fixture.yaml
```

Create local config outside the repo:

```bash
mkdir -p ~/.config/kb-api ~/.local/share/kb-api
python3 -m kb_api init-config --output ~/.config/kb-api/config.yaml
```

Edit:

```bash
vim ~/.config/kb-api/config.yaml
```

Validate and index:

```bash
python3 -m kb_api validate-config --config ~/.config/kb-api/config.yaml
python3 -m kb_api doctor --config ~/.config/kb-api/config.yaml
python3 -m kb_api reindex --config ~/.config/kb-api/config.yaml
python3 -m kb_api status --config ~/.config/kb-api/config.yaml
```

Run manually:

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
python3 -m kb_api serve --config ~/.config/kb-api/config.yaml
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
python -m kb_win_sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
notepad "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Validate and preview:

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

Run:

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
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

On Linux, verify the remote vault directory exists and is writable:

```bash
mkdir -p /home/your-linux-user/kb/KnowledgeVault
test -w /home/your-linux-user/kb/KnowledgeVault
```

Keep `sync.enabled: false` until SSH, remote path, and permissions are confirmed. Do not use GitHub as a sync backend.

## Upgrade

Pull or copy the new source code, then rerun tests and validation:

```bash
python3 -m unittest discover -s tests -v
python3 -m kb_api validate-config --config ~/.config/kb-api/config.yaml
python3 -m kb_api reindex --config ~/.config/kb-api/config.yaml
systemctl --user restart kb-api.service
```

On Windows, rerun:

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
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
2. Find the task that runs `run-kb-win-sync.bat` or `python -m kb_win_sync`.
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

- `python3 -m kb_api smoke-test --config examples/linux-config.fixture.yaml` succeeds with synthetic data.
- `python3 -m kb_api status --config <linux-config>` shows expected notes/chunks.
- `python -m kb_win_sync validate-config --config <windows-config>` reports no errors.
- No token values are printed in logs or status output.
- No vault data, `.msg`, SQLite DB, `.env`, local config, or SSH key is inside the source repository.

After uninstall:

- `systemctl --user status kb-api.service` no longer shows a running service.
- Task Scheduler no longer runs the Windows import.
- Local config/token files are removed only if intentionally deleted.
- Obsidian vault data remains wherever the user chose to keep it.
