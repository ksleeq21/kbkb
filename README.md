# kbkb

Local-first Outlook-to-Obsidian knowledge base sync와 read-only search API.

이 저장소는 소스 코드 전용이다. Obsidian vault 내용, exported email, `.msg` file, 첨부파일, SQLite database, token, SSH key, 개인 note를 source repository에 저장하지 않는다.

## 구성 요소

- `kb_win_sync`: Windows 쪽 Outlook import, Markdown rendering, state storage, 선택적 SFTP sync.
- `kb_api`: Linux 쪽 vault scanner, SQLite FTS indexer, read-only HTTP API.
- `cline_skill_obsidian_kb`: Cline/Codex skill instruction과 helper script.
- `examples`: synthetic configuration과 service template.

## 설치 개요

두 machine에 같은 source repository를 설치하되 서로 다른 optional dependency를 사용한다.

- Windows는 Outlook COM import와 선택적 SFTP sync를 위해 `.[windows]`가 필요하다.
- Linux는 indexing/search를 위해 core package가 필요하다. `.[api]`는 선택 사항이며 FastAPI/uvicorn deployment에만 필요하다.

Local config, token, vault data, `.msg` file, 첨부파일, log, SQLite database는 source repository 밖에 둔다.

전체 token, service, upgrade, uninstall 절차가 필요하면 [docs/SETUP.md](docs/SETUP.md)를 사용한다. 아래 README는 짧은 설치 경로다.

## Windows 설치

Classic Outlook이 설치된 Windows machine의 repository root에서 PowerShell로 다음을 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
kb-win-sync --help
```

Windows importer config를 만든다.

```powershell
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
```

`init-config`는 `%USERPROFILE%\KnowledgeVault`, state/log directory, SSH key parent directory를 만들고 Windows user path가 들어간 config를 생성한다.

그다음 Outlook folder picker에서 동기화할 folder 번호를 선택한다. 선택한 folder는 config에 자동으로 추가된다.

```powershell
kb-win-sync list-mailboxes --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Outlook folder path, mailbox selection, Task Scheduler 설정이 불명확하면 [docs/WINDOWS_OUTLOOK_SETUP.md](docs/WINDOWS_OUTLOOK_SETUP.md)를 사용한다. 이 문서는 Windows 전용 setup guide다.

SFTP sync를 켤 때 `sync.key_path`에 넣을 SSH key를 만들거나 확인해야 하면 [docs/WINDOWS_SSH_KEY_SETUP.md](docs/WINDOWS_SSH_KEY_SETUP.md)를 사용한다.

## Linux 설치

API와 enriched vault를 호스팅할 Linux machine의 repository root에서 다음을 실행한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
kb-api --help
```

Linux API config를 repository 밖에 만든다.

```bash
kb-api init-config --output ~/.config/kb-api/config.yaml
```

`init-config`는 현재 Linux user의 home directory 아래에 기본 vault, database parent, enrichment cache directory를 만들고, `~/.zshrc` 또는 `~/.bashrc`에 `KB_API_TOKEN`과 `KB_API_ADMIN_TOKEN` export block을 추가한다.

API를 실행하는 shell에 local-only token을 설정한다.

```bash
source ~/.zshrc  # bash를 사용하면 source ~/.bashrc
```

Linux에서 강한 token을 생성하고 systemd environment file에 저장하는 절차는 [docs/LINUX_TOKEN_SETUP.md](docs/LINUX_TOKEN_SETUP.md)를 사용한다.

config를 검증한다.

```bash
kb-api doctor --config ~/.config/kb-api/config.yaml
```

기본 standard-library server 대신 FastAPI/uvicorn으로 실행하려면 optional API dependency를 설치한다.

```bash
python -m pip install -e ".[api]"
```

Windows import, SFTP raw vault sync, Linux enrichment, reindex, API search를 하나의 완전한 workflow로 연결할 때는 [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md)를 사용한다.

## 5분 Local Smoke Test

synthetic fixture data만 사용해 Linux API index/search/read 경로를 검증한다.

```bash
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
kb-api smoke-test --config examples/linux-config.fixture.yaml
```

예상 output에는 다음이 포함된다.

```text
validate-config: ok
reindex: ok notes=2 chunks=2
search: ok query=SSO source=20_Emails/ProjectA/2026-05-19_0915__Synthetic_SSO__abc123.md
read: ok title=Synthetic SSO incident analysis
context: ok evidence=1
smoke-test: ok
next: kb-api init-config --output ~/.config/kb-api/config.yaml
```

기본 MVP HTTP server는 standard library를 사용하며 필요한 read-only endpoint를 노출한다. Optional FastAPI dependency를 설치한 deployment에서는 `kb_api.fastapi_app:create_app`을 사용할 수 있다.

## Windows 가져오기

1. `%USERPROFILE%\kb-win-sync\config.yaml`에 local config를 생성한다.
2. `vault_path`, whitelisted `outlook.folders`, 선택적 `sync`를 수정한다.
3. 실행한다.

```powershell
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync list-mailboxes --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

설정된 Outlook folder만 scan한다. 설정되지 않은 folder는 무시한다.

Daily execution은 `examples/run-kb-win-sync.bat`와 Windows Task Scheduler를 사용할 수 있다. Outlook COM access가 interactive desktop을 필요로 하면 user가 logged in 상태일 때만 실행하도록 설정한다.

Outlook을 사용할 수 없거나 folder를 찾지 못하거나 duplicate import가 보이거나 SFTP가 실패하면 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)를 사용한다.

SFTP sync를 활성화하기 전에 Windows SSH private key를 만들고 Linux에 public key를 등록해야 한다. `sync.key_path` 설정은 [docs/WINDOWS_SSH_KEY_SETUP.md](docs/WINDOWS_SSH_KEY_SETUP.md)를 참고한다.

## Linux API

1. repo 밖에 local config를 생성한다.
2. local-only token을 설정한다.

```bash
source ~/.zshrc  # bash를 사용하면 source ~/.bashrc
```

Token 생성, 확인, service environment file 설정은 [docs/LINUX_TOKEN_SETUP.md](docs/LINUX_TOKEN_SETUP.md)를 참고한다.

3. Linux에서 raw Markdown을 enrich한 뒤 enriched Markdown vault에서 index를 다시 만든다.

```bash
kb-api init-config --output ~/.config/kb-api/config.yaml
kb-api doctor --config ~/.config/kb-api/config.yaml
kb-api enrich --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
kb-api status --config ~/.config/kb-api/config.yaml
```

4. API를 시작한다.

```bash
kb-api serve --config ~/.config/kb-api/config.yaml
```

Endpoint:

- `GET /health`: 인증 없는 health check.
- `GET /health?deep=true`: 인증 없는 DB/index status check.
- `GET /search?q=...&limit=10`: bearer-token search.
- `GET /notes/by-path?path=...`: bearer-token으로 vault-relative path를 읽는다.
- `POST /context`: bearer-token으로 compact evidence bundle을 반환한다.
- `POST /admin/reindex`: admin-token reindex.

MVP에는 create, update, delete endpoint가 없다.

API response, skill script, auth header, endpoint path를 변경할 때는 [docs/API_CONTRACT.md](docs/API_CONTRACT.md)를 사용한다. 이 문서는 stable v1 contract를 정의한다.

설치 후 service, daily operation, reindex procedure를 설정할 때는 [docs/OPERATIONS.md](docs/OPERATIONS.md)를 사용한다.

Token auth, database status, search result, service startup이 예상대로 동작하지 않으면 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)를 사용한다.

## Cline/Codex Skill 설정

설정:

```bash
export KB_API_BASE_URL=http://127.0.0.1:8765
export KB_API_TOKEN='replace-with-local-token'
```

사용:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_search.py "SSO incident"
python3 cline_skill_obsidian_kb/scripts/kb_search.py "SSO incident" --limit 5 --json
python3 cline_skill_obsidian_kb/scripts/kb_read.py "20_Emails/ProjectA/example.md"
python3 cline_skill_obsidian_kb/scripts/kb_context.py "What did we decide about SSO rollback?"
```

## 보안 메모

- 검토된 network access plan이 없다면 API는 `127.0.0.1`에 bind한다.
- health가 아닌 모든 endpoint에 bearer token을 사용한다.
- vault-relative path만 사용한다. absolute path와 `..` traversal은 거부된다.
- repository test fixture는 synthetic이며 계속 synthetic이어야 한다.

새 sync/storage path가 허용 가능한지 또는 storage boundary와 token handling을 검토할 때는 [docs/SECURITY.md](docs/SECURITY.md)를 사용한다.

## 개선 계획

기능이 scope에 속하는지 판단할 때는 [docs/PRD.md](docs/PRD.md)를 사용한다. first-run UX 또는 setup quality를 개선할 때는 [docs/USABILITY_80_PLAN.md](docs/USABILITY_80_PLAN.md)와 [docs/FIRST_RUN_UX_REVIEW.md](docs/FIRST_RUN_UX_REVIEW.md)를 사용한다.

Graph search, backlink, relationship table, future graph-boosted ranking 작업을 할 때만 [docs/OBSIDIAN_GRAPH_DEVELOPMENT.md](docs/OBSIDIAN_GRAPH_DEVELOPMENT.md)를 사용한다.
