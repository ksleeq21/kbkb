# End-to-End Workflow: Windows Outlook to Linux Search

이 문서는 사용자가 Windows와 Linux에 각각 프로그램을 설치한 뒤, Outlook 이메일을 Obsidian Markdown으로 동기화하고 최종적으로 검색하는 전체 흐름을 설명한다.

## 1. Architecture

```text
Windows
  Classic Outlook
    -> kb_win_sync
    -> Windows Obsidian vault
    -> optional SFTP sync

Linux
  Raw Linux vault copy
    -> Cline CLI metadata enrichment
    -> Enriched Linux vault
    -> kb_api reindex
    -> SQLite FTS database
    -> local read-only HTTP API
    -> Cline/Codex skill scripts or direct user search
```

역할 분리:

- Windows: Outlook에서 선택한 메일함을 읽고 Markdown, `.msg`, 첨부파일을 vault에 저장한다.
- Linux: 동기화된 raw Markdown을 Cline CLI로 보강해 enriched Markdown을 만든 뒤 SQLite FTS index를 생성한다.
- Cline/Codex: Linux API를 호출해 검색 결과와 evidence를 가져온다.

중요한 원칙:

- Windows에서 생성한 raw Markdown은 Linux에서 덮어쓰지 않는다.
- Cline CLI 단계는 raw Markdown을 입력으로 받고 metadata JSON object만 출력한다.
- validator가 Cline CLI 결과를 검증한 뒤 raw Markdown에 적용해 별도의 enriched Markdown 파일을 생성한다.
- `kb_api`는 raw Markdown이 아니라 enriched Markdown vault를 reindex한다.
- 이 구조는 Cline CLI 출력과 Markdown 변환을 fixture로 테스트하기 쉽게 만든다.

## 2. Linux: Install and Smoke Test

먼저 Linux에서 API와 index path가 정상 동작하는지 synthetic fixture로 확인한다.

```bash
python3 -m unittest discover -s tests -v
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
python3 -m kb_api smoke-test --config examples/linux-config.fixture.yaml
```

성공 기준:

```text
validate-config: ok
reindex: ok notes=2 chunks=2
search: ok
read: ok
smoke-test: ok
```

FastAPI/uvicorn 배포를 사용할 경우 선택 dependency를 설치한다.

```bash
python3 -m pip install -e ".[api]"
```

## 3. Linux: Create API Config and Tokens

로컬 config와 DB directory를 만든다.

```bash
mkdir -p ~/.config/kb-api ~/.local/share/kb-api
python3 -m kb_api init-config --output ~/.config/kb-api/config.yaml
```

`~/.config/kb-api/config.yaml`에서 검색 대상 vault와 DB path를 설정한다. Cline enrichment를 사용하는 운영에서는 `vault_path`가 raw sync directory가 아니라 enriched Markdown directory를 가리켜야 한다.

```yaml
vault_path: "/home/you/kb/KnowledgeVault-Enriched"
raw_vault_path: "/home/you/kb/KnowledgeVault-Raw"
enriched_vault_path: "/home/you/kb/KnowledgeVault-Enriched"
enrichment_cache_path: "/home/you/.local/share/kb-api/enrichment-cache"
attachment_policy: "copy"
database_path: "/home/you/.local/share/kb-api/kb.sqlite"
token_env: "KB_API_TOKEN"
admin_token_env: "KB_API_ADMIN_TOKEN"
ignore_dirs:
  - ".obsidian"
  - ".trash"
  - ".git"
server:
  host: "127.0.0.1"
  port: 8765
```

API token을 생성하고 shell 또는 systemd environment file에 설정한다.

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
```

설정을 검증한다.

```bash
python3 -m kb_api validate-config --config ~/.config/kb-api/config.yaml
python3 -m kb_api doctor --config ~/.config/kb-api/config.yaml
```

## 4. Windows: Install Outlook Importer

Windows에서 classic Microsoft Outlook desktop이 필요하다. New Outlook은 MVP 대상이 아니다.

Windows optional dependency를 설치한다.

```powershell
python -m pip install -e ".[windows]"
```

로컬 설정 파일을 만든다.

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\kb-win-sync"
python -m kb_win_sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
```

## 5. Windows: Select Mailboxes

Outlook 메일함과 폴더 목록을 번호로 확인한다.

```powershell
python -m kb_win_sync list-mailboxes
```

명령은 classic Outlook을 열어 폴더 트리를 읽고 다음처럼 출력한다.

```text
1. \Mailbox - User Name
2.   \Mailbox - User Name\Inbox
3.     \Mailbox - User Name\Inbox\_KB
4.       \Mailbox - User Name\Inbox\_KB\ProjectA
5.       \Mailbox - User Name\Inbox\_KB\ProjectB
동기화 시키고 싶은 메일함 Index(예: 1,2,3,5):
```

동기화할 폴더 번호를 쉼표로 입력한다.

```text
4,5
```

명령은 `outlook.folders` 아래에 붙일 수 있는 YAML snippet을 출력한다.

```yaml
    - name: "projecta"
      outlook_path: "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/projecta"
      tags:
        - "email"
        - "mailbox/projecta"
      save_msg: true
      save_attachments: true
```

출력된 snippet을 `%USERPROFILE%\kb-win-sync\config.yaml`에 붙이고, `name`, `target_folder`, `tags`를 프로젝트 규칙에 맞게 다듬는다.

권장 운영 방식:

- Inbox 전체를 바로 import하지 않는다.
- Outlook에 `_KB` 같은 import 전용 폴더를 만든다.
- 사용자가 검색 가능하게 만들고 싶은 메일만 `_KB` 하위 폴더로 옮긴다.

## 6. Windows: Configure Vault and Sync

Windows config는 대략 다음 형태다.

```yaml
vault_path: "D:/KnowledgeVault"
state_path: "C:/Users/you/AppData/Local/kb-win-sync/state/import-state.json"
log_path: "C:/Users/you/AppData/Local/kb-win-sync/logs/kb-win-sync.log"
outlook:
  folders:
    - name: "project-a"
      outlook_path: "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/ProjectA"
      tags:
        - "email"
        - "project/project-a"
      save_msg: true
      save_attachments: true
sync:
  enabled: false
  host: "linux-dev.example.internal"
  port: 22
  username: "your-linux-user"
  remote_path: "/home/your-linux-user/kb/KnowledgeVault-Raw"
  key_path: "C:/Users/you/.ssh/id_rsa"
```

SFTP sync를 켜기 전에 Windows에서 SSH 접속을 먼저 확인한다.

```powershell
ssh your-linux-user@linux-dev.example.internal
```

Linux에서 raw sync directory가 있고 쓰기 가능한지 확인한다.

```bash
mkdir -p /home/your-linux-user/kb/KnowledgeVault-Raw
test -w /home/your-linux-user/kb/KnowledgeVault-Raw
```

SSH와 remote path가 확인된 뒤 `sync.enabled: true`로 바꾼다.

## 7. Windows: Validate, Preview, Import

설정을 검증한다.

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

실제 파일을 쓰기 전에 dry-run으로 가져올 메일을 확인한다.

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

성공 기준:

- configured folder만 스캔한다.
- import 예정 메일의 sender, received, subject, target path가 출력된다.
- Markdown, `.msg`, 첨부파일, state file은 아직 쓰지 않는다.

문제가 없으면 실제 import를 실행한다.

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

생성되는 vault 구조 예:

```text
D:/KnowledgeVault/
  20_Emails/
    ProjectA/
      2026/05/2026-05-19_0915__SSO장애원인분석__a1b2c3d4.md
  90_Attachments/
    email/
      a1b2c3d4/
        original.msg
        report.xlsx
```

Markdown frontmatter에는 Outlook metadata, folder tags, attachment paths가 들어간다. 같은 메일을 다시 import해도 state file의 message key로 중복을 피한다.

이 단계에서 만들어지는 Markdown은 raw Markdown이다. Linux의 Cline CLI enrichment 단계가 테스트 가능하도록, 이 파일은 이후 단계에서 직접 덮어쓰지 않는다.

## 8. Windows: Schedule Daily Import

수동 import가 성공한 뒤에만 Task Scheduler를 등록한다.

제공되는 wrapper:

```text
examples/run-kb-win-sync.bat
```

기본 내용:

```bat
@echo off
set CONFIG=%USERPROFILE%\kb-win-sync\config.yaml
python -m kb_win_sync --config "%CONFIG%"
```

Task Scheduler 권장값:

- Create Task를 사용한다.
- Outlook COM이 background session에서 동작하지 않으면 "Run only when user is logged on"을 선택한다.
- Daily trigger를 설정한다.
- Action은 wrapper `.bat`를 실행한다.
- Start in은 repository 또는 설치된 package working directory로 둔다.
- 수동으로 Task를 한 번 실행해 history와 log를 확인한다.

## 9. Linux: Enrich Raw Markdown with Cline CLI

Windows에서 동기화된 raw Markdown이 Linux에 도착하면, 검색 index를 만들기 전에 Cline CLI로 metadata를 보강한다.

권장 directory 구조:

```text
/home/you/kb/
  KnowledgeVault-Raw/
    20_Emails/ProjectA/raw-email.md
    90_Attachments/email/...
  KnowledgeVault-Enriched/
    20_Emails/ProjectA/raw-email.md
    90_Attachments/email/...
  cline-enrichment-cache/
    20_Emails/ProjectA/raw-email.metadata.json
```

계약:

- Input: `KnowledgeVault-Raw` 아래의 원본 Markdown
- Cline CLI output: 정해진 JSON object only
- Validator: Cline 출력 문법, 필수 필드, 금지 필드, tag taxonomy를 검증
- Output: `KnowledgeVault-Enriched` 아래의 새 Markdown
- Raw Markdown은 수정하지 않음
- Attachment policy: `copy`. `90_Attachments` 등 Markdown이 아닌 파일은 enriched vault로 복사한다. Symlink는 Windows/SFTP/Obsidian 경계에서 깨질 수 있으므로 사용하지 않는다.

권장 처리 흐름:

```text
raw-email.md
  -> python3 -m kb_api enrich --config ~/.config/kb-api/config.yaml
  -> raw-email.metadata.json
  -> validator
  -> frontmatter merge in memory
  -> KnowledgeVault-Enriched/.../raw-email.md
```

Cline CLI에는 전체 frontmatter를 다시 쓰게 하지 않는다. 다음처럼 검색 보강 metadata만 JSON으로 출력하게 한다.

```json
{
  "tags": ["개발망", "회의록"],
  "llm_tags": ["인프라", "개발환경"],
  "llm_summary": "개발망 미팅 회의록을 공유한 이메일."
}
```

validator는 다음을 거부해야 한다.

- `source_id`, `message_id`, `conversation_id`, `received`, `from`, `to`, `cc` 같은 원본 metadata 수정
- YAML/JSON 문법 오류
- 과도하게 많은 tag
- 허용되지 않은 tag 또는 normalization 불가능한 tag
- vault 외부 path

실행:

```bash
python3 -m kb_api enrich --config ~/.config/kb-api/config.yaml
```

Cline CLI를 호출하지 않고 cache fixture만으로 테스트할 때:

```bash
python3 -m kb_api enrich --config ~/.config/kb-api/config.yaml --use-cache-only
```

테스트 방식:

```text
fixtures/raw/email.md
fixtures/cline-output/email.metadata.json
expected/enriched/email.md
```

이렇게 두면 Cline CLI를 실제로 호출하지 않아도 `raw Markdown + Cline output -> enriched Markdown` 변환을 golden fixture로 검증할 수 있다.

## 10. Linux: Reindex Enriched Vault

enriched Markdown 생성이 끝나면 `kb_api`가 enriched vault를 reindex한다. `kb_api`는 raw vault가 아니라 `KnowledgeVault-Enriched`를 바라봐야 한다.

```bash
python3 -m kb_api validate-config --config ~/.config/kb-api/config.yaml
python3 -m kb_api doctor --config ~/.config/kb-api/config.yaml
python3 -m kb_api reindex --config ~/.config/kb-api/config.yaml
python3 -m kb_api status --config ~/.config/kb-api/config.yaml
```

`kb_api`는 enriched vault의 Markdown을 읽어 SQLite에 저장한다.

- `notes`: Markdown 파일 metadata와 body
- `chunks`: 검색용 본문 조각
- `chunks_fts`: SQLite full-text search index

현재 MVP API는 read-only이며 vault 파일을 수정하지 않는다.

## 11. Linux: Run the API

수동 실행:

```bash
export KB_API_TOKEN='replace-with-generated-token'
export KB_API_ADMIN_TOKEN='replace-with-different-generated-token'
python3 -m kb_api serve --config ~/.config/kb-api/config.yaml
```

다른 shell에서 확인:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

systemd user service로 실행:

```bash
mkdir -p ~/.config/systemd/user
cp examples/kb-api.service ~/.config/systemd/user/kb-api.service
systemctl --user daemon-reload
systemctl --user enable --now kb-api.service
systemctl --user status kb-api.service
```

## 12. User Search

사용자는 API를 직접 호출할 수 있다.

```bash
curl -sS 'http://127.0.0.1:8765/search?q=개발망%20회의록&type=email&limit=10' \
  -H "Authorization: Bearer $KB_API_TOKEN"
```

응답 예:

```json
{
  "results": [
    {
      "path": "20_Emails/ProjectA/example.md",
      "title": "개발망 미팅 회의록 공유",
      "type": "email",
      "sender": "Kim <kim@example.com>",
      "received": "2026-05-19T09:15:00+09:00",
      "folder": "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA",
      "tags": ["email", "project/project-a"],
      "chunk_index": 0,
      "matched_fields": ["body"],
      "metadata": {
        "type": "email"
      },
      "score": -0.123,
      "excerpt": "개발망 미팅 회의록 전달드립니다."
    }
  ]
}
```

특정 note를 읽는다.

```bash
curl -sS 'http://127.0.0.1:8765/notes/by-path?path=20_Emails/ProjectA/example.md' \
  -H "Authorization: Bearer $KB_API_TOKEN"
```

## 13. Cline/Codex Search

Linux shell에서 skill script 환경변수를 설정한다.

```bash
export KB_API_BASE_URL=http://127.0.0.1:8765
export KB_API_TOKEN='replace-with-generated-token'
```

검색:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_search.py "개발망 회의록"
python3 cline_skill_obsidian_kb/scripts/kb_search.py "개발망 회의록" --limit 5 --json
```

읽기:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_read.py "20_Emails/ProjectA/example.md"
```

AI context bundle:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_context.py "개발망 회의록 관련해서 지난번에 어떤 결정이 있었어?"
```

Cline/Codex는 source path, sender, received date 같은 metadata를 근거로 답해야 한다. evidence가 약하거나 없으면 그 사실을 명확히 말한다.

## 14. Future Graph Extension

현재 기본 워크플로우는 Outlook metadata, folder tags, Cline CLI 보강 metadata, Markdown body, SQLite FTS를 중심으로 검색한다.

`docs/OBSIDIAN_GRAPH_DEVELOPMENT.md`는 다음 확장을 정의한다.

- graph/metadata boost를 통한 검색 순위 강화
- `[[wiki links]]`, backlinks, tags, folders, people, conversations, attachments graph table
- graph-boosted search
- 첨부파일 내부 텍스트 검색

Graph 확장은 raw/enriched Markdown과 SQLite index가 안정화된 뒤 추가한다.
