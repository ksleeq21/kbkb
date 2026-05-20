# 설정, Token, Uninstall

이 문서는 설치, 토큰 설정, 서비스 등록, 제거 절차를 한 곳에 모은 운영용 가이드다.

설치부터 검색까지의 전체 사용자 흐름은 `docs/END_TO_END_WORKFLOW.md`를 먼저 참고한다.

## Token 정책

다음 데이터는 소스 저장소에 올리면 안 된다.

- Obsidian vault contents
- imported email Markdown file 일체
- `.msg` original
- 첨부파일
- SQLite database
- log
- local config file
- API token
- SSH private key
- `.env` file

### KB API Token 설정

Linux API는 local bearer token을 사용한다.

- `KB_API_TOKEN`: `/search`, `/notes/by-path`, `/context`용 일반 read-only API token.
- `KB_API_ADMIN_TOKEN`: `/admin/reindex`용 admin token.

Linux에서 강한 local token을 생성한다.

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

shell session에 token을 설정한다.

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
```

user-level systemd에서는 repo 밖의 private environment file을 우선 사용한다.

```bash
mkdir -p ~/.config/kb-api
chmod 700 ~/.config/kb-api
printf 'KB_API_TOKEN=%s\nKB_API_ADMIN_TOKEN=%s\n' 'replace-with-generated-token' 'replace-with-different-generated-token' > ~/.config/kb-api/env
chmod 600 ~/.config/kb-api/env
```

그다음 service file에 다음을 추가한다.

```ini
EnvironmentFile=%h/.config/kb-api/env
```

이 environment file을 커밋하지 않는다.

### Cline/Codex Skill Token 설정

skill script는 다음을 읽는다.

```bash
export KB_API_BASE_URL=http://127.0.0.1:8765
export KB_API_TOKEN='replace-with-generated-token'
```

admin token은 필요하지 않다.

### SFTP/SSH Key 설정

Windows-to-Linux sync는 활성화되면 SSH/SFTP를 사용한다. SSH private key path는 local Windows config에만 필요하다.

```yaml
sync:
  enabled: true
  host: "linux-dev.example.internal"
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "C:/Users/you/.ssh/id_rsa"
```

SSH private key나 local config file을 절대 커밋하지 않는다.

Windows에서 새 key를 생성하고 Linux `authorized_keys`에 public key를 등록하는 절차는 `docs/WINDOWS_SSH_KEY_SETUP.md`를 참고한다.

## 설치

먼저 source tree를 editable mode로 설치한다. 이렇게 하면 아래에서 사용하는 짧은 `kb-api`, `kb-win-sync` command가 노출된다.

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

editable install을 사용할 수 없으면 legacy module command인 `python3 -m kb_api`와 `python -m kb_win_sync`를 대신 사용한다.

## 첫 실행 경로

첫 성공 setup은 다음 순서로 진행한다.

1. editable command를 설치하고 synthetic smoke test를 실행한다.
2. Linux: API config와 token을 만든다.
3. Linux: enriched vault path를 만들거나 확인한 뒤 reindex 후 API를 시작한다.
4. Linux: `/health`, `/health?deep=true`, `/search`를 검증한다.
5. Windows: Outlook import config를 만든다.
6. Windows: `list-mailboxes --config <path>`를 실행하고 mailbox index를 선택해 config에 자동 추가한다.
7. Windows: config를 검증하고 `--dry-run`을 실행한다.
8. Windows: import를 수동으로 한 번 실행한다.
9. Windows: 수동 import가 동작한 뒤에만 Task Scheduler를 활성화한다.
10. Linux: raw Markdown에서 enriched Markdown으로 Cline CLI enrichment를 실행한다.
11. Linux: enriched vault를 reindex한다.
12. Cline/Codex: API를 대상으로 `kb_search.py`를 실행한다.

전체 usability review와 추가 improvement candidate는 `docs/FIRST_RUN_UX_REVIEW.md`를 참고한다.

### Linux API

source repository에서:

```bash
python -m unittest discover -s tests -v
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
kb-api smoke-test --config examples/linux-config.fixture.yaml
```

repo 밖에 local config를 만든다.

```bash
kb-api init-config --output ~/.config/kb-api/config.yaml
```

`init-config`는 현재 user의 home directory 기준으로 기본 vault, raw vault, database parent, enrichment cache directory를 함께 생성한다.

수정한다.

```bash
vim ~/.config/kb-api/config.yaml
```

먼저 검증한다.

```bash
kb-api validate-config --config ~/.config/kb-api/config.yaml
kb-api doctor --config ~/.config/kb-api/config.yaml
```

Windows가 raw Markdown을 Linux로 sync한 뒤 enrich하고 index한다.

```bash
kb-api enrich --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
kb-api status --config ~/.config/kb-api/config.yaml
```

수동으로 실행한다.

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
kb-api serve --config ~/.config/kb-api/config.yaml
```

다른 shell에서 검증한다.

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

### Linux systemd Service 설정

user service를 설치한다.

```bash
mkdir -p ~/.config/systemd/user
cp examples/kb-api.service ~/.config/systemd/user/kb-api.service
```

path와 token handling을 수정한다.

```bash
vim ~/.config/systemd/user/kb-api.service
```

권장 service token pattern:

```ini
EnvironmentFile=%h/.config/kb-api/env
```

포함된 `examples/kb-api.service`는 이미 이 pattern을 사용한다. 그래도 machine에 맞게 `WorkingDirectory`와 `ExecStart` path를 수정해야 한다.

시작한다.

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-api.service
systemctl --user status kb-api.service
```

### Windows Outlook Import 설정

optional Windows dependency를 설치한다.

```powershell
python -m pip install -e ".[windows]"
```

repo 밖에 local config를 만든다.

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\kb-win-sync"
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync list-mailboxes --config "$env:USERPROFILE\kb-win-sync\config.yaml"
notepad "$env:USERPROFILE\kb-win-sync\config.yaml"
```

`list-mailboxes --config <path>`는 Outlook mailbox와 folder를 numeric index와 함께 출력한 뒤 다음을 묻고, 선택한 folder를 config의 `outlook.folders` 아래에 자동으로 추가한다.

```text
동기화 시키고 싶은 메일함 Index(예: 1,2,3,5):
```

자동 추가된 `outlook.folders` 항목을 local config에서 확인하고 필요에 따라 `name`, `target_folder`, `tags`를 조정한다.

검증하고 미리 확인한다.

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

실행한다.

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

### Windows Task Scheduler 설정

자세한 Outlook folder 선택과 Task Scheduler GUI 단계는 `docs/WINDOWS_OUTLOOK_SETUP.md`를 참고한다.

script 안의 config path를 수정하거나 default path에 맞춘 뒤 `examples/run-kb-win-sync.bat`를 action target으로 사용한다.

권장 설정:

- Outlook COM이 background session에서 실행되지 않으면 user가 logged on 상태일 때만 실행한다.
- repository directory 또는 설치된 package environment에서 시작한다.
- Outlook을 정상적으로 사용할 수 있는 시간 이후 매일 실행한다.
- stdout/stderr는 Task Scheduler history로 capture하거나 repo 밖의 local wrapper script에서 redirect한다.

수동 `--dry-run`과 수동 import가 모두 동작한 뒤에만 schedule을 등록한다.

### SFTP Sync 사전 확인

`sync.enabled: true`를 설정하기 전에 Windows에서 SSH/SFTP를 독립적으로 검증한다.

```powershell
ssh your-linux-user@linux-dev.example.internal
```

아직 SSH key를 만들지 않았다면 먼저 `docs/WINDOWS_SSH_KEY_SETUP.md`에 따라 Windows private key를 생성하고 Linux에 public key를 등록한다.

Linux에서는 remote raw vault directory가 존재하고 writable인지 확인한다. `kb_api`가 사용하는 enriched vault directory도 만든다.

```bash
mkdir -p /home/your-linux-user/kb/KnowledgeVault-Raw
mkdir -p /home/your-linux-user/kb/KnowledgeVault-Enriched
test -w /home/your-linux-user/kb/KnowledgeVault-Raw
```

SSH, remote path, permission이 확인될 때까지 `sync.enabled: false`를 유지한다. GitHub를 sync backend로 사용하지 않는다.

`kb_win_sync`는 raw vault로 sync해야 한다. Linux Cline CLI enrichment 단계는 raw vault를 읽고 별도의 enriched vault를 써야 한다. `kb_api.vault_path`는 enriched vault로 설정한다.

## Upgrade 절차

새 source code를 pull하거나 복사한 뒤 test와 validation을 다시 실행한다.

```bash
python -m unittest discover -s tests -v
kb-api validate-config --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
systemctl --user restart kb-api.service
```

Windows에서는 다시 실행한다.

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

## Uninstall 절차

### Linux API Service 중지 및 제거

```bash
systemctl --user disable --now kb-api.service
rm -f ~/.config/systemd/user/kb-api.service
systemctl --user daemon-reload
```

더 이상 필요하지 않을 때만 local API config, token, DB를 제거한다.

```bash
rm -rf ~/.config/kb-api
rm -rf ~/.local/share/kb-api
```

개인 knowledge data를 의도적으로 제거하려는 경우가 아니면 Obsidian vault를 삭제하지 않는다.

### Windows Scheduled Import 제거

Task Scheduler에서:

1. Task Scheduler를 연다.
2. `run-kb-win-sync.bat` 또는 `kb-win-sync`를 실행하는 task를 찾는다.
3. 먼저 비활성화한다.
4. daily import가 필요 없음을 확인한 뒤 삭제한다.

더 이상 필요하지 않을 때만 local Windows config/state/log를 제거한다.

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\kb-win-sync"
```

개인 knowledge data를 의도적으로 제거하려는 경우가 아니면 Windows Obsidian vault를 삭제하지 않는다.

### Python Package 설치 제거

이 repository에서 editable로 설치했다면:

```bash
python3 -m pip uninstall kbkb
```

Windows:

```powershell
python -m pip uninstall kbkb
```

source checkout에서 module만 직접 실행했고 package를 설치하지 않았다면 제거할 Python package가 없을 수 있다.

## 검증 Checklist

setup 후:

- `kb-api smoke-test --config examples/linux-config.fixture.yaml`가 synthetic data로 성공한다.
- `kb-api status --config <linux-config>`가 예상한 notes/chunks를 보여준다.
- `kb-win-sync validate-config --config <windows-config>`가 error를 보고하지 않는다.
- log나 status output에 token value가 출력되지 않는다.
- source repository 안에 vault data, `.msg`, SQLite DB, `.env`, local config, SSH key가 없다.

uninstall 후:

- `systemctl --user status kb-api.service`가 더 이상 running service를 보여주지 않는다.
- Task Scheduler가 더 이상 Windows import를 실행하지 않는다.
- local config/token file은 의도적으로 삭제한 경우에만 제거된다.
- Obsidian vault data는 사용자가 보관하기로 한 위치에 남아 있다.
