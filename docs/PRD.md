# PRD: Outlook-to-Obsidian 지식 베이스 동기화 및 API

## 1. 제품 요약

이 project는 선택한 Microsoft Outlook email과 text note를 Obsidian vault로 가져오고, 그 vault를 Windows에서 Linux development environment로 동기화한 뒤, Cline/Codex skill 또는 다른 AI coding assistant가 사용할 수 있는 read-only search API를 제공하는 local-first personal knowledge base pipeline을 만든다.

시스템은 source code와 personal knowledge content를 분리해서 관리해야 하는 enterprise environment를 전제로 설계한다.

## 2. 배경

사용자는 주로 Windows에서 문서 작업과 email communication을 수행하며, Microsoft Office LTSC Professional Plus 2021에 포함된 Microsoft Outlook을 사용한다.

Software development는 별도의 Linux machine에서 수행한다. Windows에서 VS Code Remote SSH로 Linux environment에 접속해 개발하며, Cline과 Codex는 Linux development environment에서 실행된다.

사용자는 과거 email과 개인 text note를 검색 가능하고 knowledge base로 활용 가능하게 만들고 싶다. Obsidian은 note를 local Markdown file로 vault folder에 저장하므로 local-first knowledge management에 적합하다.

하지만 source data와 AI execution environment는 분리되어 있다.

Windows:
- Microsoft Outlook
- 기존 text note
- Obsidian desktop
- Windows Obsidian vault

Linux:
- Development environment
- VS Code server
- Cline/Codex execution
- API server
- Obsidian vault의 synced copy

Cline은 Linux development environment에서 실행되고 local Windows data에 대한 remote MCP access가 없으므로, 선호하는 접근은 raw Markdown을 Linux로 sync하고, Linux에서 Cline CLI로 별도의 enriched vault를 만든 뒤, enriched vault 위에 Linux-based HTTP API를 노출하는 것이다. Cline은 skill 또는 script를 통해 이 API를 호출한다.

## 3. 목표

### 3.1 주요 목표

1. Windows에서 선택한 Outlook email을 Markdown file로 Obsidian vault에 import한다.
2. 사용자가 import할 Outlook folder를 설정할 수 있게 한다.
3. sender, recipients, subject, received time, Outlook folder, conversation ID, attachments 같은 유용한 email metadata를 보존한다.
4. 가능하면 원본 email을 `.msg`로 저장한다.
5. email attachment를 deterministic folder structure로 Obsidian vault 안에 저장한다.
6. manual import와 scheduled daily import를 지원한다.
7. GitHub를 storage로 사용하지 않고 Windows Obsidian vault를 Linux vault copy로 synchronize한다.
8. enriched vault를 index하고 read-only HTTP API를 노출하는 Linux service를 만든다.
9. Cline/Codex skill이 Linux API를 통해 knowledge base content를 search/read할 수 있게 한다.
10. 시스템을 local-first, enterprise-safe, internal use에 적합하게 유지한다.

### 3.2 보조 목표

1. Obsidian vault의 기존 text note를 지원한다.
2. project-based tagging과 folder mapping을 지원한다.
3. imported email과 note에 대한 keyword search를 지원한다.
4. date, sender, folder, tag, type filter를 지원한다.
5. AI tool을 위한 compact evidence bundle을 반환하는 context API를 지원한다.
6. 모든 component를 실행, debug, 확장하기 쉽게 만든다.
7. 불필요한 dependency, paid service, SaaS service, 불명확한 license obligation을 피한다.

## 4. 비목표

첫 version에서는 다음을 하지 않는다.

1. Obsidian vault content를 source repository에 저장하지 않는다.
2. email, note, attachment를 external SaaS service에 upload하지 않는다.
3. Obsidian Sync 또는 Obsidian Publish에 의존하지 않는다.
4. MVP에서 Microsoft Graph API permission을 요구하지 않는다.
5. Outlook add-in marketplace installation을 요구하지 않는다.
6. Windows Obsidian vault를 network에 직접 노출하지 않는다.
7. 첫 version에서 Cline에 write/update/delete API를 제공하지 않는다.
8. MVP에서 embedding 기반 full RAG system을 만들지 않는다.
9. 모든 Outlook email을 기본으로 import하지 않는다.
10. 사용자가 명시적으로 설정하지 않은 sensitive folder를 import하지 않는다.
11. MVP에서 모든 attachment가 text-index 가능하다고 가정하지 않는다.

## 5. 사용자

### 5.1 주요 사용자

Primary user는 다음 특성을 가진 software engineer다.

- Windows를 Outlook, document, general office work에 사용한다.
- Microsoft Office LTSC Professional Plus 2021을 사용한다.
- Obsidian으로 personal knowledge를 관리한다.
- Linux를 software development environment로 사용한다.
- Windows에서 VS Code Remote SSH로 Linux에 접속한다.
- Linux environment에서 Cline/Codex를 사용한다.
- task 해결 중 AI tool이 과거 email과 note를 검색하기를 원한다.
- GitHub를 personal file storage로 사용하지 못하는 enterprise restriction을 따라야 한다.

### 5.2 AI 도구 사용자

Cline/Codex는 Linux API를 통해 knowledge base를 소비하는 secondary user다. 다음을 할 수 있어야 한다.

- 관련 historical email과 note를 search한다.
- 특정 note를 path 또는 ID로 read한다.
- user question에 대한 concise context bundle을 요청한다.
- 답변에서 source path와 email metadata를 cite한다.

## 6. 상위 아키텍처

```text
[Windows]
Microsoft Outlook LTSC 2021
        │
        │ COM automation
        ▼
kb-win-sync
        │
        ├─ Reads configured Outlook folders
        ├─ Converts emails to Markdown
        ├─ Saves .msg originals
        ├─ Saves attachments
        ├─ Updates Windows Obsidian vault
        └─ Syncs changed files to Linux over SSH/SFTP or rsync-compatible mechanism
        │
        ▼
Windows Obsidian Vault
D:\KnowledgeVault
        │
        │ File sync, not GitHub
        ▼
[Linux]
Raw Linux Vault Copy
/home/<user>/kb/KnowledgeVault-Raw
        │
        │ Cline CLI metadata enrichment
        ▼
Enriched Linux Vault
/home/<user>/kb/KnowledgeVault-Enriched
        │
        ▼
kb-api
        │
        ├─ Scans enriched Markdown files
        ├─ Parses YAML frontmatter
        ├─ Indexes content into SQLite FTS
        ├─ Provides read-only HTTP API
        └─ Serves search/context/read requests
        │
        ▼
Cline/Codex Skill
        │
        ├─ Calls kb-api
        ├─ Retrieves evidence
        └─ Uses results in AI answers
```

## 7. 필수 구성 요소

제품은 두 main application과 하나의 lightweight AI integration package로 구성된다.

### 7.1 구성 요소 1: kb-win-sync

Windows application이며 다음을 담당한다.

1. configured folder에서 Outlook email을 읽는다.
2. imported email을 Windows Obsidian vault에 쓴다.
3. email metadata를 YAML frontmatter로 저장한다.
4. email body를 Markdown으로 저장한다.
5. 원본 `.msg` file을 저장한다.
6. attachment를 저장한다.
7. 이미 import한 message를 추적한다.
8. 변경된 vault file을 Linux vault copy로 synchronize한다.
9. manual execution과 scheduled execution을 지원한다.

### 7.2 구성 요소 2: kb-api

Linux application이며 다음을 담당한다.

1. Linux에서 생성된 enriched Obsidian vault를 읽는다.
2. Markdown file과 YAML frontmatter를 parse한다.
3. note와 email content를 SQLite에 index한다.
4. full-text search를 제공한다.
5. note read API를 제공한다.
6. AI-friendly context API를 제공한다.
7. Linux development environment에서 local service로 실행된다.

### 7.3 구성 요소 3: cline-skill-obsidian-kb

Cline/Codex skill package이며 다음을 담당한다.

1. AI가 언제 knowledge base를 사용해야 하는지 설명한다.
2. Linux API를 호출하는 script를 제공한다.
3. source citation behavior를 강제한다.
4. 지원하지 않는 write operation을 방지한다.
5. AI assistant에 structured evidence를 반환한다.

### 7.4 구성 요소 4: Linux Cline CLI 보강 단계

Linux enrichment step이며 다음을 담당한다.

1. Windows에서 sync된 raw Markdown을 읽는다.
2. raw Markdown을 input으로 Cline CLI를 호출한다.
3. tags, `llm_tags`, `llm_summary` 같은 structured metadata output을 받는다.
4. Cline CLI output을 검증한다.
5. raw Markdown은 변경하지 않는다.
6. indexing을 위한 별도의 enriched Markdown file을 쓴다.
7. raw Markdown과 저장된 Cline output을 이용한 fixture-based test를 지원한다.

## 8. 기능 요구사항

### 8.1 Windows 앱: kb-win-sync

#### FR-WIN-001: 설정 가능한 Outlook Folder Import

App은 사용자가 import할 Outlook folder를 설정할 수 있어야 한다.

Configuration은 다음 형태를 지원한다.

```yaml
outlook:
  folders:
    - name: "project-a"
      outlook_path: "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/ProjectA"
      tags:
        - email
        - project/project-a
      save_msg: true
      save_attachments: true
```

Acceptance criteria:

- 사용자는 config file을 수정해 Outlook folder를 추가하거나 제거할 수 있다.
- configured folder만 import된다.
- unconfigured folder는 무시된다.
- folder-specific tag가 imported Markdown file에 적용된다.
- folder-specific target path가 지켜진다.

#### FR-WIN-002: Outlook LTSC 2021 호환성

App은 Microsoft Office LTSC Professional Plus 2021에 포함된 Microsoft Outlook과 동작해야 한다.

Implementation expectation:

- PowerShell 또는 Python `pywin32`를 통한 Outlook COM automation을 사용한다.
- MVP에서 Microsoft Graph API를 요구하지 않는다.
- New Outlook을 요구하지 않는다.

Acceptance criteria:

- locally installed Outlook desktop client에 연결할 수 있다.
- configured folder를 enumerate할 수 있다.
- `MailItem` object를 read할 수 있다.
- subject, sender, recipients, received time, body, attachments, 가능한 conversation metadata를 access할 수 있다.

#### FR-WIN-003: Email-to-Markdown Conversion

각 imported email은 하나의 Markdown file로 저장해야 한다.

Recommended file path:

```text
20_Emails/<FolderName>/<YYYY>/<MM>/<YYYY-MM-DD_HHMM>__<sanitized-subject>__<message-key>.md
```

Example:

```text
20_Emails/ProjectA/2026/05/2026-05-19_0915__SSO장애원인분석__a1b2c3d4.md
```

Acceptance criteria:

- 하나의 email은 하나의 Markdown file을 만든다.
- file name은 deterministic하다.
- unsafe file name character는 제거하거나 대체한다.
- 긴 subject는 안전하게 truncate한다.
- duplicate file name은 message key 또는 hash로 피한다.
- Markdown file은 Obsidian에서 읽기 쉽다.

#### FR-WIN-004: YAML Frontmatter

각 imported email Markdown file은 YAML frontmatter를 포함해야 한다.

Required fields:

```yaml
---
type: email
source: outlook
folder: "Inbox/_KB/ProjectA"
subject: "SSO 장애 원인 분석 요청"
from: "Kim <kim@example.com>"
to:
  - "Hong <hong@example.com>"
cc: []
received: 2026-05-19T09:15:00+09:00
conversation_id: "..."
message_id: "<...>"
message_key: "a1b2c3d4"
imported_at: 2026-05-19T09:30:00+09:00
attachments:
  - "90_Attachments/email/a1b2c3d4/report.xlsx"
original_msg: "90_Attachments/email/a1b2c3d4/original.msg"
tags:
  - email
  - project/project-a
---
```

Acceptance criteria:

- frontmatter는 valid YAML이다.
- missing field는 graceful하게 처리한다.
- timestamp는 ISO-8601 format을 사용한다.
- attachment path는 vault root 기준 relative path다.
- original `.msg` path는 vault root 기준 relative path다.
- tag는 folder configuration에서 포함된다.

#### FR-WIN-005: Email Body Formatting 처리

Email body는 frontmatter 아래에 작성한다.

Recommended structure:

```markdown
# <Email Subject>

## Metadata 정보

- From: ...
- To: ...
- Cc: ...
- Received: ...
- Outlook folder: ...

## 본문

<plain text email body>

## 첨부파일

- [[relative/path/to/attachment]]
- [[relative/path/to/original.msg]]
```

Acceptance criteria:

- body는 Obsidian에서 읽기 쉽다.
- MVP에서는 plain text body를 우선한다.
- HTML-to-Markdown conversion은 MVP에서 optional이다.
- 기본 whitespace cleanup을 적용한다.
- attachment는 Markdown file에서 link된다.

#### FR-WIN-006: 원본 `.msg` 저장

설정된 경우 app은 원본 email을 `.msg` file로 저장해야 한다.

Recommended path:

```text
90_Attachments/email/<message-key>/original.msg
```

Acceptance criteria:

- `save_msg: true`이면 원본 `.msg`가 저장된다.
- 저장된 file은 Outlook에서 열 수 있다.
- Markdown frontmatter에 vault-relative `original_msg` path가 포함된다.
- Markdown Attachments section이 저장된 `.msg` path를 link한다.
- `.msg` 저장 실패는 log에 남기지만 전체 import를 중단하지 않는다.

Implementation note:

현재 config model은 `save_msg`를 노출하지만 quality-complete behavior를 위해 Outlook adapter가 source `MailItem`의 save hook을 전달하고 importer가 Markdown rendering 전에 `.msg` artifact를 써야 한다. Test는 CI에서 Outlook이 없어도 검증할 수 있도록 fake Outlook item 또는 fake artifact writer를 사용해야 한다.

#### FR-WIN-007: Save Attachments

설정된 경우 app은 email attachment를 저장해야 한다.

Recommended path:

```text
90_Attachments/email/<message-key>/<sanitized-attachment-name>
```

Acceptance criteria:

- `save_attachments: true`이면 일반 attachment가 모두 저장된다.
- attachment file name은 sanitize된다.
- duplicate attachment name은 disambiguate된다.
- attachment path는 frontmatter에 기록된다.
- attachment path는 Markdown body에 link된다.
- import summary의 attachment와 `.msg` counter는 실제 저장된 artifact를 반영한다.
- 개별 attachment 저장 실패는 log에 남는다.

Implementation note:

Importer는 Markdown renderer를 호출하기 전에 attachment를 저장해 `EmailAttachment.saved_path`를 채워야 한다. Attachment save failure는 vault 자체가 writable하지 않은 경우가 아니라면 run-level failure가 아니라 per-file failure여야 한다.

#### FR-WIN-008: Duplicate Import 방지

App은 같은 email을 여러 번 import하지 않아야 한다.

Duplicate detection은 stable message key를 사용한다.

Preferred key priority:

1. Internet Message-ID가 있으면 사용한다.
2. Conversation ID + received time + sender + subject hash를 사용한다.
3. fallback으로 Outlook EntryID hash.

Acceptance criteria:

- importer를 다시 실행해도 duplicate Markdown file이 생기지 않는다.
- imported message key는 local state file에 저장된다.
- state file은 run 사이에 유지된다.
- email이 이미 존재하면 force option이 없는 한 skip한다.

#### FR-WIN-009: Local State 관리

App은 local import state를 유지해야 한다.

Recommended state path:

```text
D:\kb-tools\state\outlook-import-state.json
```

State should include:

```json
{
  "imported_messages": {
    "a1b2c3d4": {
      "subject": "SSO 장애 원인 분석 요청",
      "received": "2026-05-19T09:15:00+09:00",
      "markdown_path": "20_Emails/ProjectA/2026/05/...",
      "imported_at": "2026-05-19T09:30:00+09:00"
    }
  }
}
```

Acceptance criteria:

- successful import 후 state가 update된다.
- process 실패 시 state가 corrupt되지 않는다.
- 가능한 곳에서는 state write가 atomic이다.
- 이전 state backup을 보관할 수 있다.

#### FR-WIN-010: Manual Trigger

App은 manual execution을 지원해야 한다.

Acceptance criteria:

- 사용자는 PowerShell에서 app을 실행할 수 있다.
- 사용자는 `.bat` shortcut으로 app을 실행할 수 있다.
- log는 화면에 보이거나 log file에 기록된다.
- exit code는 success 또는 failure를 나타낸다.

Example:

```text
powershell.exe -ExecutionPolicy Bypass -File D:\kb-tools\kb-win-sync.ps1
```

#### FR-WIN-011: Scheduled Execution

App은 Windows Task Scheduler를 통한 scheduled execution을 지원해야 한다.

Acceptance criteria:

- app은 하루 한 번 unattended로 실행될 수 있다.
- interactive input 없이 실행될 수 있다.
- scheduled run result를 log에 남긴다.
- COM automation이 허용하면 Outlook이 열려 있지 않아도 처리한다.
- Outlook access가 실패하면 error를 log에 남기고 clean하게 종료한다.

#### FR-WIN-012: Windows-to-Linux Vault Sync 구현

App은 GitHub를 사용하지 않고 Windows vault를 Linux vault copy로 sync해야 한다.

Recommended sync methods:

1. SSH 위의 SFTP.
2. `scp` 또는 `sftp` command-line tool.
3. environment에서 가능하면 `rsync`.
4. 내부 승인이 있는 경우 SMB mount.

MVP recommendation:

```text
SFTP over SSH with key-based authentication
```

Acceptance criteria:

- 새 file이 Linux로 copy된다.
- 변경된 file이 Linux로 copy된다.
- manifest feature가 활성화된 뒤 unchanged file은 반복 copy되지 않는다.
- sync는 GitHub를 요구하지 않는다.
- sync는 external SaaS를 요구하지 않는다.
- sync error는 log에 남는다.
- testing을 위해 config에서 sync를 disable할 수 있다.

#### FR-WIN-013: Incremental Sync Manifest 관리

첫 successful sync 이후 매번 모든 file을 copy하지 않도록 app은 sync manifest를 유지해야 한다.

Recommended manifest path:

```text
D:\KnowledgeVault\.kb-sync-manifest.json
```

Manifest example:

```json
{
  "20_Emails/ProjectA/2026/05/mail.md": {
    "size": 15342,
    "sha256": "abc...",
    "modified_at": "2026-05-19T09:30:00+09:00"
  }
}
```

Acceptance criteria:

- app은 file hash 또는 신뢰 가능한 modified metadata를 계산한다.
- app은 new/changed file을 식별한다.
- 첫 manifest가 작성된 뒤 new/changed file만 upload한다.
- manifest를 안전하게 저장한다.
- 가능한 곳에서는 manifest write가 atomic이다.
- sync가 중간에 실패하면 이전 manifest를 보존하고 다음 run에서 unsynced file을 retry한다.

Quality note:

Implementation은 `file_digest`, `load_manifest`, `save_manifest`를 `SftpSyncer.sync`에 연결해 blind full-vault upload가 아니라 manifest diff로 upload eligibility를 결정해야 한다.

### 8.2 Linux 앱: kb-api

#### FR-LINUX-001: Vault Path 설정

Linux app은 indexing할 configured enriched vault path를 읽어야 한다. Windows에서 sync된 raw Markdown은 indexer가 직접 읽지 않고 enrichment step이 읽는다.

Example config:

```yaml
vault_path: "/home/kangsan/kb/KnowledgeVault-Enriched"
raw_vault_path: "/home/kangsan/kb/KnowledgeVault-Raw"
enriched_vault_path: "/home/kangsan/kb/KnowledgeVault-Enriched"
enrichment_cache_path: "/home/kangsan/.local/share/kb-api/enrichment-cache"
attachment_policy: "copy"
database_path: "/home/kangsan/kb/kb.sqlite"
token_env: "KB_API_TOKEN"
admin_token_env: "KB_API_ADMIN_TOKEN"
server:
  host: "127.0.0.1"
  port: 8765
```

Acceptance criteria:

- vault path는 configurable이다.
- database path는 configurable이다.
- API host와 port는 configurable이다.
- secret은 hardcode하지 않고 environment variable에서 읽는다.

#### FR-LINUX-002: Markdown Scanner

App은 vault 아래 Markdown file을 scan해야 한다.

Acceptance criteria:

- `.md` file을 recursive하게 찾는다.
- hidden/system folder는 별도 설정이 없으면 무시한다.
- full reindex를 수행할 수 있다.
- 구현한 경우 file modification metadata 기반 incremental reindex를 수행할 수 있다.
- malformed Markdown을 graceful하게 처리한다.

#### FR-LINUX-003: YAML Frontmatter Parser 구현

App은 note에서 YAML frontmatter를 parse해야 한다.

Acceptance criteria:

- frontmatter가 있으면 추출한다.
- frontmatter가 없는 file도 처리한다.
- type, subject, from, received, tags, folder 같은 field를 추출한다.
- invalid YAML은 log에 남기고 indexer를 crash시키지 않는다.

#### FR-LINUX-004: SQLite Index

App은 note metadata와 content를 SQLite에 index해야 한다.

Recommended tables:

```sql
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  type TEXT,
  title TEXT,
  created_at TEXT,
  updated_at TEXT,
  received TEXT,
  sender TEXT,
  folder TEXT,
  tags TEXT,
  frontmatter_json TEXT,
  body TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  note_id TEXT NOT NULL,
  path TEXT NOT NULL,
  heading TEXT,
  chunk_index INTEGER,
  body TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  title,
  heading,
  body,
  path UNINDEXED,
  note_id UNINDEXED,
  tokenize = 'trigram'
);
```

Acceptance criteria:

- note는 stable ID로 저장된다.
- path는 unique하다.
- email metadata는 query 가능하다.
- content는 searchable하다.
- reindex는 vault content에서 database를 rebuild할 수 있다.

Search quality requirement:

Korean compound word와 partial string이 흔하므로, local SQLite build가 지원하면 indexer는 FTS5 `trigram` tokenizer를 우선해야 한다. trigram이 없으면 default tokenizer로 fallback하고 diagnostics 또는 log에 이를 보여야 한다.

#### FR-LINUX-005: Full-Text Search API 제공

App은 search API를 제공해야 한다.

Endpoint:

```http
GET /search
```

Parameters:

- `q`: required search query
- `limit`: optional, default 10
- `type`: optional, e.g. email, note
- `tag`: optional
- `sender`: optional
- `folder`: optional
- `after`: optional ISO date
- `before`: optional ISO date

Example:

```http
GET /search?q=SSO%20장애&type=email&tag=project/project-a&limit=10
```

Response example:

```json
{
  "query": "SSO 장애",
  "results": [
    {
      "id": "note-id",
      "path": "20_Emails/ProjectA/2026/05/2026-05-19_0915__SSO장애__a1b2c3d4.md",
      "title": "SSO 장애 원인 분석 요청",
      "type": "email",
      "received": "2026-05-19T09:15:00+09:00",
      "sender": "Kim <kim@example.com>",
      "folder": "Inbox/_KB/ProjectA",
      "tags": ["email", "project/project-a"],
      "score": 12.43,
      "excerpt": "SSO 인증 실패는 IdP metadata 갱신 이후 발생..."
    }
  ]
}
```

Acceptance criteria:

- Search는 relevant note를 반환한다.
- Search result에는 path, title, type, metadata, score, excerpt가 포함된다.
- type, tag, sender, folder, after, before filter를 지원한다.
- filter는 `/search`, `/context`, skill script에서 일관되게 구현된다.
- search는 configured vault 밖 file을 노출하지 않는다.

#### FR-LINUX-006: Note Read API 제공

App은 note를 읽는 API를 제공해야 한다.

Endpoint options:

```http
GET /notes/{id}
GET /notes/by-path?path=<relative-path>
```

Acceptance criteria:

- API는 note metadata와 body를 반환한다.
- path access는 configured vault로 제한된다.
- path traversal attempt는 거부된다.
- missing note는 404를 반환한다.
- API는 note를 수정하지 않는다.

#### FR-LINUX-007: AI Tool용 Context API

App은 AI-friendly context endpoint를 제공해야 한다.

Endpoint:

```http
POST /context
```

Request example:

```json
{
  "query": "ProjectA SSO 장애 원인과 관련된 과거 메일을 찾아줘",
  "filters": {
    "type": "email",
    "tags": ["project/project-a"],
    "after": "2026-01-01"
  },
  "limit": 8
}
```

Response example:

```json
{
  "query": "ProjectA SSO 장애 원인과 관련된 과거 메일을 찾아줘",
  "evidence": [
    {
      "path": "20_Emails/ProjectA/2026/05/2026-05-19_0915__SSO장애__a1b2c3d4.md",
      "title": "SSO 장애 원인 분석 요청",
      "type": "email",
      "received": "2026-05-19T09:15:00+09:00",
      "sender": "Kim <kim@example.com>",
      "excerpt": "SSO 인증 실패는 IdP metadata 갱신 이후 발생...",
      "why_relevant": "Query terms matched title and body."
    }
  ]
}
```

Acceptance criteria:

- endpoint는 Cline/Codex에 적합한 compact evidence를 반환한다.
- 각 evidence item은 source path와 metadata를 포함한다.
- response는 기본적으로 너무 많은 text를 반환하지 않는다.
- response는 repeatable AI usage에 충분히 deterministic하다.

#### FR-LINUX-008: Reindex API

App은 vault reindex를 위한 admin endpoint를 제공해야 한다.

Endpoint:

```http
POST /admin/reindex
```

Acceptance criteria:

- reindex는 manual trigger가 가능하다.
- reindex는 SQLite index를 rebuild 또는 update한다.
- reindex에는 authentication이 필요하다.
- reindex progress와 error를 log에 남긴다.
- reindex는 vault file을 수정하지 않는다.

#### FR-LINUX-009: Authentication

API는 모든 non-health endpoint에 token을 요구해야 한다.

Recommended header:

```http
Authorization: Bearer <KB_API_TOKEN>
```

Acceptance criteria:

- `/health`는 unauthenticated일 수 있다.
- `/search`, `/notes`, `/context`, `/admin/reindex`는 authentication이 필요하다.
- token은 environment variable에서 읽는다.
- invalid token은 401 또는 403을 반환한다.
- token은 절대 log에 남기지 않는다.

#### FR-LINUX-010: Service Execution

API는 Linux service로 실행 가능해야 한다.

Acceptance criteria:

- command line에서 실행할 수 있다.
- systemd 아래에서 실행할 수 있다.
- restart할 수 있다.
- log는 stdout 또는 log file에 기록된다.
- 기본 bind address는 `127.0.0.1`이다.

### 8.3 Cline/Codex Skill: cline-skill-obsidian-kb 구성

#### FR-SKILL-001: Skill Package 구조

Skill package는 Cline-compatible skill directory에 배치해야 한다.

Recommended structure:

```text
.cline/
  skills/
    obsidian-kb/
      SKILL.md
      scripts/
        kb_search.py
        kb_context.py
        kb_read.py
```

Acceptance criteria:

- Skill instruction은 `SKILL.md`에 작성된다.
- script는 Linux API를 호출한다.
- script는 environment variable에서 API base URL과 token을 읽는다.
- script는 AI consumption을 위해 JSON 또는 readable text output을 출력한다.

#### FR-SKILL-002: Skill Behavior Instruction 작성

`SKILL.md`는 사용자가 다음을 물을 때 AI가 KB API를 사용하도록 지시해야 한다.

- 과거 email
- 이전 결정
- project history
- incident
- vendor/customer discussion
- meeting note
- 기존 personal note
- private historical context가 필요한 모든 질문

Acceptance criteria:

- skill은 AI가 memory로 추측하지 않도록 지시한다.
- skill은 AI가 KB API를 먼저 호출하도록 지시한다.
- skill은 source path와 metadata를 cite하도록 지시한다.
- skill은 unsupported write API를 호출하지 않도록 지시한다.
- skill은 evidence가 약할 때 그 사실을 말하도록 지시한다.

#### FR-SKILL-003: Search Script

Skill은 search script를 포함해야 한다.

Example usage:

```bash
python .cline/skills/obsidian-kb/scripts/kb_search.py "ProjectA SSO 장애"
```

Acceptance criteria:

- script는 `GET /search`를 호출한다.
- script는 query와 optional limit을 지원한다.
- script는 authorization token을 전달한다.
- script는 result를 명확히 출력한다.

#### FR-SKILL-004: Context Script

Skill은 context script를 포함해야 한다.

Example usage:

```bash
python .cline/skills/obsidian-kb/scripts/kb_context.py "지난 3개월 ProjectA SSO 장애 관련 메일 요약"
```

Acceptance criteria:

- script는 `POST /context`를 호출한다.
- script는 query, limit, type, tag, sender, folder, after, before filter를 지원한다.
- script는 source evidence를 출력한다.
- script는 AI prompt consumption에 적합하다.

#### FR-SKILL-005: Read Script

Skill은 note read script를 포함해야 한다.

Example usage:

```bash
python .cline/skills/obsidian-kb/scripts/kb_read.py "20_Emails/ProjectA/2026/05/example.md"
```

Acceptance criteria:

- script는 `GET /notes/by-path`를 호출한다.
- script는 empty path를 거부한다.
- script는 note metadata와 body를 출력한다.
- script는 file을 수정하지 않는다.

## 9. 데이터 모델

### 9.1 Vault 구조

권장 Windows vault path:

```text
D:\KnowledgeVault
```

권장 Linux vault path:

```text
/home/kangsan/kb/KnowledgeVault
```

Recommended folder structure:

```text
KnowledgeVault/
  00_Inbox/
  10_Notes/
  20_Emails/
    General/
    ProjectA/
  30_Projects/
  80_References/
  90_Attachments/
    email/
  99_Index/
```

### 9.2 Email Markdown 파일

Example:

```markdown
---
type: email
source: outlook
folder: "Inbox/_KB/ProjectA"
subject: "SSO 장애 원인 분석 요청"
from: "Kim <kim@example.com>"
to:
  - "Hong <hong@example.com>"
cc: []
received: 2026-05-19T09:15:00+09:00
conversation_id: "..."
message_id: "<...>"
message_key: "a1b2c3d4"
imported_at: 2026-05-19T09:30:00+09:00
attachments:
  - "90_Attachments/email/a1b2c3d4/report.xlsx"
original_msg: "90_Attachments/email/a1b2c3d4/original.msg"
tags:
  - email
  - project/project-a
---

# SSO 장애 원인 분석 요청

## Metadata 정보

- From: Kim <kim@example.com>
- To: Hong <hong@example.com>
- Received: 2026-05-19 09:15
- Outlook folder: Inbox/_KB/ProjectA

## 본문

메일 본문...

## 첨부파일

- [[90_Attachments/email/a1b2c3d4/report.xlsx]]
- [[90_Attachments/email/a1b2c3d4/original.msg]]
```

### 9.3 Config 파일

권장 Windows config file:

```text
D:\kb-tools\config.yaml
```

Example:

```yaml
vault:
  windows_path: "D:/KnowledgeVault"

state:
  path: "D:/kb-tools/state/outlook-import-state.json"

logging:
  path: "D:/kb-tools/logs/kb-win-sync.log"
  level: "INFO"

sync:
  enabled: true
  method: "sftp"
  host: "linux-dev-server"
  port: 22
  user: "kb-sync"
  remote_path: "/home/kangsan/kb/KnowledgeVault-Raw"
  private_key: "C:/Users/kangsan/.ssh/kb_sync_ed25519"
  manifest_path: "D:/KnowledgeVault/.kb-sync-manifest.json"

outlook:
  folders:
    - name: "general"
      outlook_path: "\\Mailbox - Kangsan Lee\\Inbox\\_KB\\General"
      target_folder: "20_Emails/General"
      tags:
        - email
        - kb/general
      save_msg: true
      save_attachments: true

    - name: "project-a"
      outlook_path: "\\Mailbox - Kangsan Lee\\Inbox\\_KB\\ProjectA"
      target_folder: "20_Emails/ProjectA"
      tags:
        - email
        - project/project-a
      save_msg: true
      save_attachments: true
```

### 9.4 Linux API Config

권장 Linux config file:

```text
/home/kangsan/kb/kb-api.yaml
```

Example:

```yaml
vault_path: "/home/kangsan/kb/KnowledgeVault-Enriched"
raw_vault_path: "/home/kangsan/kb/KnowledgeVault-Raw"
enriched_vault_path: "/home/kangsan/kb/KnowledgeVault-Enriched"
enrichment_cache_path: "/home/kangsan/.local/share/kb-api/enrichment-cache"
attachment_policy: "copy"
database_path: "/home/kangsan/kb/kb.sqlite"
token_env: "KB_API_TOKEN"
admin_token_env: "KB_API_ADMIN_TOKEN"
server:
  host: "127.0.0.1"
  port: 8765

index:
  ignore_dirs:
    - ".obsidian"
    - ".trash"
  include_extensions:
    - ".md"
```

## 10. Security 및 Privacy 요구사항

### SEC-001: GitHub Vault Storage 금지

System은 email, note, attachment, vault content를 source repository에 저장하면 안 된다.

Acceptance criteria:

- vault data는 source repository에 commit되지 않는다.
- `.gitignore`는 vault/database/log가 우발적으로 포함되는 것을 막는다.
- documentation은 vault data를 GitHub에 저장하지 말라고 경고한다.
- test fixture에는 실제 email이나 sensitive note가 없어야 한다.

### SEC-002: Local-First Storage

모든 knowledge base data는 승인된 local Windows/Linux machine에 남아야 한다.

Acceptance criteria:

- external SaaS dependency가 없다.
- email import를 위한 external API call이 없다.
- KB API에서 external LLM call을 하지 않는다.
- Obsidian Sync dependency가 없다.
- Obsidian Publish dependency가 없다.

### SEC-003: Read-Only AI Access 유지

첫 version은 Cline/Codex에 read-oriented API만 노출해야 한다.

Acceptance criteria:

- Cline/Codex는 search/read할 수 있다.
- Cline/Codex는 note를 create/update/delete할 수 없다.
- admin reindex는 authenticated이다.
- write API는 MVP에서 구현하지 않는다.

### SEC-004: API Token

Linux API는 bearer token을 사용해야 한다.

Acceptance criteria:

- token은 environment variable에서 읽는다.
- token은 non-health endpoint에 필요하다.
- token은 hardcode하지 않는다.
- token은 log에 남기지 않는다.

### SEC-005: Path Traversal Protection 구현

Linux API는 path traversal을 막아야 한다.

Acceptance criteria:

- `../`를 사용하는 request는 거부된다.
- absolute path는 internal에서 명시적으로 허용하지 않는 한 거부된다.
- 모든 note path는 configured vault root 아래로 resolve된다.
- vault 밖 file은 read할 수 없다.

### SEC-006: Sensitive Data Control 적용

Importer는 whitelist folder model을 사용해야 한다.

Acceptance criteria:

- configured Outlook folder만 import된다.
- 기본적으로 모든 mailbox folder import는 지원하지 않는다.
- 사용자가 config에 folder를 명시적으로 추가해야 한다.
- log에는 full email body를 포함하지 않는다.
- log는 sensitive metadata를 과도하게 남기지 않아야 한다.

## 11. 비기능 요구사항

### NFR-001: 단순성

MVP는 수동으로 실행하고 debug하기 충분히 단순해야 한다.

Acceptance criteria:

- Windows app은 PowerShell에서 실행할 수 있다.
- Linux API는 shell에서 실행할 수 있다.
- config file은 사람이 읽을 수 있는 YAML이다.
- log는 사람이 읽을 수 있다.

### NFR-002: 신뢰성

System은 partial failure를 안전하게 처리해야 한다.

Acceptance criteria:

- 한 email import 실패가 전체 run을 중단하지 않는다.
- 한 attachment 저장 실패는 log에 남는다.
- sync failure는 local vault를 corrupt하지 않는다.
- state file은 안전하게 update된다.
- app 재실행은 idempotent하다.

### NFR-003: 성능

MVP는 realistic personal knowledge base를 지원해야 한다.

Target scale:

- Emails: 10,000+
- Markdown notes: 10,000+
- Attachments: best effort, 전부 index하지는 않음

Acceptance criteria:

- 작은 daily batch import는 빠르게 끝나야 한다.
- search는 몇 초 안에 반환되어야 한다.
- reindex는 local use에 허용 가능한 수준이어야 한다.
- 가능한 경우 incremental sync는 매 run마다 전체 vault copy를 피해야 한다.

### NFR-004: 이식성

Project는 user-specific value를 hardcode하지 않아야 한다.

Acceptance criteria:

- path는 configurable이다.
- Outlook folder는 configurable이다.
- API host/port는 configurable이다.
- token은 environment variable로 제공된다.
- script는 documented command로 동작한다.

### NFR-005: 유지보수성

Codebase는 Codex/Cline이 수정하기 쉬워야 한다.

Acceptance criteria:

- module boundary가 명확하다.
- README가 명확하다.
- core function test가 있다.
- 불필요한 framework complexity가 없다.
- Python에는 type hint를 사용한다.
- logging과 error handling이 합리적이다.

## 12. 권장 Repository 구조

Source code는 source repository에 저장할 수 있다. vault data는 repository에 저장하면 안 된다.

Recommended repository name:

```text
obsidian-kb-pipeline
```

Recommended structure:

```text
obsidian-kb-pipeline/
  README.md
  PRD.md
  DESIGN.md
  PLAN.md

  kb_win_sync/
    README.md
    pyproject.toml
    src/
      kb_win_sync/
        __init__.py
        config.py
        outlook_reader.py
        markdown_writer.py
        attachment_saver.py
        state_store.py
        sync_sftp.py
        manifest.py
        logging_config.py
        cli.py
    tests/
      test_filename_sanitize.py
      test_markdown_writer.py
      test_manifest.py

  kb_api/
    README.md
    pyproject.toml
    src/
      kb_api/
        __init__.py
        config.py
        vault_scanner.py
        frontmatter.py
        indexer.py
        search.py
        api.py
        auth.py
        models.py
    tests/
      test_frontmatter.py
      test_path_security.py
      test_search.py

  cline_skill_obsidian_kb/
    SKILL.md
    scripts/
      kb_search.py
      kb_context.py
      kb_read.py

  examples/
    config.win.example.yaml
    config.linux.example.yaml
    systemd/
      kb-api.service
    windows/
      run-kb-win-sync.bat
      task-scheduler-notes.md

  .gitignore
```

## 13. .gitignore 요구사항

Repository는 real vault data, database, log, secret이 우발적으로 commit되는 것을 막아야 한다.

Required `.gitignore` entries:

```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/
dist/
build/
*.egg-info/

# Secrets
.env
*.key
*.pem
*.p12
*.pfx
config.yaml
config.local.yaml
*.secret.*

# Logs
logs/
*.log

# Runtime state
state/
*.sqlite
*.sqlite3
*.db
*.db-wal
*.db-shm

# Obsidian vault data must never be committed
KnowledgeVault/
vault/
*.msg

# Attachments
90_Attachments/

# OS/editor
.DS_Store
Thumbs.db
.vscode/
.idea/
```

## 14. MVP 범위

MVP는 최소한의 유용한 local-first workflow를 제공해야 한다.

MVP Must Have:

1. Windows config file.
2. Outlook folder whitelist.
3. configured Outlook folder import를 지원한다.
4. email-to-Markdown conversion.
5. `.msg` original 저장.
6. attachment 저장.
7. duplicate 방지를 위한 import state 유지.
8. SFTP를 사용한 Windows vault file의 Linux sync.
9. raw Markdown에서 enriched Markdown으로 Linux Cline CLI enrichment.
10. Linux enriched vault scanner를 제공한다.
11. SQLite FTS index.
12. `/health` endpoint.
13. `/search` endpoint.
14. `/notes/by-path` endpoint.
15. bearer token authentication.
16. `kb_search.py`, `kb_read.py`를 포함한 Cline skill.
17. setup/execution documentation.

MVP Should Have:

1. incremental sync manifest.
2. `/context` endpoint.
3. `POST /admin/reindex`.
4. Windows Task Scheduler guide를 제공한다.
5. Linux systemd service file을 제공한다.
6. basic tests.

MVP Can Defer:

1. embedding-based semantic search.
2. graph-based note relationship.
3. attachment text extraction.
4. high-fidelity HTML-to-Markdown conversion.
5. Outlook calendar import.
6. two-way sync.
7. note editing API.
8. MCP server wrapper.
9. Obsidian plugin development.

## 15. 사용자 Workflow

### 15.1 Manual Email Capture Workflow 절차

1. 사용자가 중요한 Outlook email을 받거나 찾는다.
2. 사용자가 email을 configured Outlook folder, 예를 들어 `Inbox/_KB/ProjectA`로 move/copy한다.
3. 사용자가 `kb-win-sync`를 manual로 실행한다.
4. `kb-win-sync`가 email을 Windows Obsidian vault로 import한다.
5. `kb-win-sync`가 changed file을 Linux로 sync한다.
6. Linux enrichment가 raw Markdown에 대해 Cline CLI를 실행한다.
7. enrichment step이 별도의 enriched Markdown file을 쓴다.
8. `kb-api`가 enriched Markdown file을 index한다.
9. 사용자가 Cline/Codex에 해당 topic을 질문한다.
10. Cline/Codex가 KB API를 호출하고 evidence를 사용한다.

### 15.2 Daily Automatic Import Workflow 절차

1. 사용자가 낮 동안 유용한 email을 configured Outlook `_KB` folder에 넣는다.
2. Windows Task Scheduler가 하루 한 번 `kb-win-sync`를 실행한다.
3. email이 Windows Obsidian vault로 import된다.
4. changed file이 Linux로 sync된다.
5. Linux Cline CLI enrichment가 자동 또는 on demand로 실행된다.
6. Linux reindex가 enriched vault 대상으로 자동 또는 on demand로 실행된다.
7. Cline/Codex는 updated knowledge base를 search할 수 있다.

### 15.3 AI Search Workflow 절차

Example user request:

```text
지난 3개월 동안 ProjectA SSO 장애와 관련된 메일과 노트를 찾아서 원인, 결정사항, 남은 액션아이템을 정리해줘.
```

Expected AI behavior:

1. Cline/Codex는 private historical knowledge가 필요함을 감지한다.
2. Cline/Codex는 obsidian-kb skill을 사용한다.
3. Skill script가 `kb-api /context` 또는 `/search`를 호출한다.
4. API가 relevant note와 email을 반환한다.
5. AI가 `/notes/by-path`로 high-value note를 읽는다.
6. AI가 evidence와 함께 summarize한다.
7. 가능한 경우 AI가 source path, sender, received date를 cite한다.

## 16. API 명세

### 16.1 GET /health

Response:

```json
{
  "status": "ok"
}
```

### 16.2 GET /search

Request:

```http
GET /search?q=<query>&limit=10&type=email&tag=project/project-a
Authorization: Bearer <token>
```

Response:

```json
{
  "query": "SSO 장애",
  "results": [
    {
      "id": "abc123",
      "path": "20_Emails/ProjectA/2026/05/example.md",
      "title": "SSO 장애 원인 분석 요청",
      "type": "email",
      "received": "2026-05-19T09:15:00+09:00",
      "sender": "Kim <kim@example.com>",
      "folder": "Inbox/_KB/ProjectA",
      "tags": ["email", "project/project-a"],
      "score": 12.43,
      "excerpt": "SSO 인증 실패는..."
    }
  ]
}
```

### 16.3 GET /notes/by-path

Request:

```http
GET /notes/by-path?path=20_Emails/ProjectA/2026/05/example.md
Authorization: Bearer <token>
```

Response:

```json
{
  "id": "abc123",
  "path": "20_Emails/ProjectA/2026/05/example.md",
  "title": "SSO 장애 원인 분석 요청",
  "type": "email",
  "frontmatter": {
    "type": "email",
    "source": "outlook",
    "subject": "SSO 장애 원인 분석 요청"
  },
  "body": "# SSO 장애 원인 분석 요청\n\n..."
}
```

### 16.4 POST /context

Request:

```json
{
  "query": "ProjectA SSO 장애 원인",
  "filters": {
    "type": "email",
    "tags": ["project/project-a"]
  },
  "limit": 8
}
```

Response:

```json
{
  "query": "ProjectA SSO 장애 원인",
  "evidence": [
    {
      "path": "20_Emails/ProjectA/2026/05/example.md",
      "title": "SSO 장애 원인 분석 요청",
      "type": "email",
      "received": "2026-05-19T09:15:00+09:00",
      "sender": "Kim <kim@example.com>",
      "excerpt": "SSO 인증 실패는...",
      "why_relevant": "Matched query terms in title and body."
    }
  ]
}
```

### 16.5 POST /admin/reindex

Request:

```http
POST /admin/reindex
Authorization: Bearer <token>
```

Response:

```json
{
  "status": "ok",
  "indexed_notes": 1234,
  "indexed_chunks": 4567
}
```

## 17. CLI 요구사항

### 17.1 Windows CLI

Command:

```powershell
kb-win-sync --config D:\kb-tools\config.yaml
```

Useful options:

```text
--config <path>
--dry-run
--import-only
--sync-only
--folder <name>
--force
--verbose
```

Acceptance criteria:

- `--dry-run`은 import될 대상을 보여준다.
- `--import-only`는 sync를 skip한다.
- `--sync-only`는 Outlook import를 skip한다.
- `--folder`는 import를 configured folder 하나로 제한한다.
- `--verbose`는 logging을 늘린다.

### 17.2 Linux CLI

Commands:

```bash
kb-api reindex --config ~/kb/kb-api.yaml
kb-api serve --config ~/kb/kb-api.yaml
```

Acceptance criteria:

- `reindex`는 vault를 index한다.
- `serve`는 API server를 시작한다.
- 두 command는 같은 config file을 읽는다.

## 18. Logging 요구사항

Windows app은 다음을 log해야 한다.

- run start/end
- config path
- configured folder 수
- scanned email 수
- imported email 수
- skipped duplicate 수
- saved attachment 수
- sync upload 수
- error와 warning

Windows app은 다음을 log하면 안 된다.

- full email body
- full attachment content
- API token
- SSH private key content를 log에 남기지 않는다

Linux app은 다음을 log해야 한다.

- API server start
- vault path
- reindex start/end
- indexed file 수
- malformed frontmatter warning
- search error
- token value 없는 authentication failure

Linux app은 다음을 log하면 안 된다.

- API token
- 기본적으로 full note content
- 기본적으로 sensitive email body

## 19. Error Handling 요구사항

Windows app은 다음을 처리해야 한다.

- Outlook not available
- config file missing
- invalid Outlook folder path 처리
- email body read failure 처리
- attachment save failure
- `.msg` save failure
- vault path missing
- SSH/SFTP connection failure 처리
- remote path missing
- state file corruption

Expected behavior:

- error를 log에 남긴다.
- 안전할 때는 continue한다.
- fatal error는 non-zero exit code로 종료한다.
- vault를 의도적으로 corrupt하지 않는다.
- source Outlook email을 삭제하지 않는다.

Linux app은 다음을 처리해야 한다.

- vault path missing
- SQLite open failure
- invalid Markdown
- invalid YAML frontmatter
- path traversal attempt
- missing note path
- empty search query
- invalid token
- reindex failure

Expected behavior:

- 적절한 HTTP status code를 반환한다.
- 유용한 diagnostic을 log에 남긴다.
- API error에서 sensitive internal detail 노출을 피한다.

## 20. Testing 요구사항

### 20.1 Unit Tests

Required tests:

`kb_win_sync`:
- filename sanitization
- message key generation
- Markdown rendering
- frontmatter generation
- state store read/write 검증
- manifest diff logic

`kb_api`:
- frontmatter parsing
- vault path safety
- note indexing
- search query handling
- auth token handling
- path 기반 note read

### 20.2 Integration Tests

fake test fixture만 사용한다. 실제 email을 포함하지 않는다.

Recommended fixtures:

```text
tests/fixtures/vault/
  20_Emails/ProjectA/2026/05/sample-email.md
  10_Notes/sample-note.md
```

Required integration tests:

- fixture vault를 index한다.
- search가 expected fixture note를 반환한다.
- read-by-path가 expected note를 반환한다.
- path traversal이 거부된다.
- unauthorized request가 거부된다.

### 20.3 Manual Tests

Manual Windows test:

1. Outlook folder `Inbox/_KB/General`을 만든다.
2. test email 하나를 folder로 copy한다.
3. `kb-win-sync`를 실행한다.
4. Windows vault에 Markdown file이 생겼는지 확인한다.
5. `.msg` file이 `90_Attachments` 아래에 생겼는지 확인한다.
6. attachment가 저장되었는지 확인한다.
7. `kb-win-sync`를 다시 실행한다.
8. duplicate Markdown file이 생기지 않았는지 확인한다.

Manual Linux test:

1. Linux에 raw vault가 있는지 확인한다.
2. Cline CLI enrichment를 실행한다.
3. enriched Markdown이 존재하고 raw Markdown이 변경되지 않았는지 확인한다.
4. enriched vault를 대상으로 reindex를 실행한다.
5. API server를 시작한다.
6. `/health`를 호출한다.
7. `/search`를 호출한다.
8. `/notes/by-path`를 호출한다.
9. Cline skill script를 호출한다.

## 21. Documentation 요구사항

Project는 다음을 포함해야 한다.

1. `README.md`
2. `PRD.md`
3. `DESIGN.md`
4. `PLAN.md`
5. Windows setup guide.
6. Linux setup guide.
7. Cline skill setup guide를 제공한다.
8. Security notes.
9. Troubleshooting guide.

README는 다음을 설명해야 한다.

- project가 하는 일
- project가 하지 않는 일
- GitHub에 vault data를 저장하면 안 되는 이유
- Outlook folder 설정 방법
- Windows import 실행 방법
- Linux sync 방법
- Linux API 실행 방법
- Cline skill 사용 방법

## 22. 권장 구현 선택지

Windows app 권장 implementation:

```text
Python + pywin32 + paramiko + pyyaml
```

Alternative:

```text
PowerShell + Outlook COM + OpenSSH sftp
```

Recommendation:

maintainability와 testability가 더 중요하면 Python을 사용한다. 가장 빠른 Windows automation MVP가 목표이면 PowerShell을 사용한다.

Linux app 권장 implementation:

```text
Python + FastAPI + SQLite FTS5 + pyyaml
```

Recommended packages:

```text
fastapi
uvicorn
pydantic
pyyaml
python-frontmatter or custom parser
```

Sync preferred MVP:

```text
SFTP over SSH
```

Avoid:

```text
GitHub
External cloud drives
External SaaS sync services
```

## 23. Milestone

### Milestone 1: Repository Skeleton 구성

Deliverables:

- repository structure
- `README.md`
- `PRD.md`
- `.gitignore`
- example config file
- empty package skeleton

Acceptance criteria:

- repository에는 real vault data가 없다.
- project는 Codex/Cline에서 열 수 있다.
- basic command가 documented되어 있다.

### Milestone 2: Windows Import MVP 구현

Deliverables:

- config parser
- Outlook folder reader
- Markdown writer
- `.msg` saver
- attachment saver
- state store
- manual CLI

Acceptance criteria:

- configured Outlook folder 하나를 import할 수 있다.
- re-run이 email을 duplicate하지 않는다.
- Markdown이 Windows vault에 나타난다.
- `.msg`와 attachment가 저장된다.

### Milestone 3: Windows-to-Linux Sync MVP 구현

Deliverables:

- SFTP sync implementation
- sync config
- basic manifest 또는 simple upload logic
- sync logging

Acceptance criteria:

- Windows vault file이 Linux raw vault로 copy된다.
- sync는 import 후 실행될 수 있다.
- sync failure는 log에 남는다.

### Milestone 3.5: Linux Cline CLI Enrichment MVP 구현

Deliverables:

- raw Markdown input reader 구현
- Cline CLI invocation wrapper 구현
- structured metadata output capture 구현
- metadata validator
- enriched Markdown writer
- raw Markdown과 Cline output을 위한 golden fixture test

Acceptance criteria:

- raw Markdown은 절대 overwrite되지 않는다.
- 같은 raw Markdown과 saved Cline output은 같은 enriched Markdown을 만든다.
- invalid Cline output은 raw 또는 enriched Markdown을 수정하지 않고 reject된다.
- enrichment 성공 후 `kb-api`가 enriched vault를 index할 수 있다.

### Milestone 4: Linux Index 및 Search API 구현

Deliverables:

- vault scanner
- frontmatter parser
- SQLite schema
- reindex command
- FastAPI server
- `/health`, `/search`, `/notes/by-path`

Acceptance criteria:

- enriched vault를 index할 수 있다.
- search가 imported email을 반환한다.
- note read가 path로 동작한다.
- API는 bearer token을 요구한다.

### Milestone 5: Cline Skill 구성

Deliverables:

- `SKILL.md`
- `kb_search.py`
- `kb_read.py`
- optional `kb_context.py`

Acceptance criteria:

- Cline/Codex가 script를 호출할 수 있다.
- script는 Linux API를 호출한다.
- result는 source path와 metadata를 포함한다.
- skill instruction은 unsupported write operation을 막는다.

### Milestone 6: Automation 및 Hardening

Deliverables:

- Windows Task Scheduler guide 작성
- Linux systemd service
- admin reindex endpoint 또는 timer
- additional tests
- troubleshooting guide

Acceptance criteria:

- daily import를 자동으로 실행할 수 있다.
- Linux API를 service로 실행할 수 있다.
- system은 common failure에서 recover할 수 있다.
- documentation은 repeat setup에 충분하다.

## 24. 열린 질문

1. Windows의 정확한 Outlook mailbox display name은 무엇인가?
2. 첫 MVP에 포함할 Outlook folder는 무엇인가?
3. Windows vault path는 무엇인가?
4. Linux vault path는 무엇인가?
5. 사용자 environment에서 Windows-to-Linux SSH/SFTP가 허용되는가?
6. Windows에서 삭제된 file을 Linux에서도 삭제할 것인가, 아니면 append/update only sync로 둘 것인가?
7. attachment를 즉시 sync할 것인가, 아니면 큰 attachment를 제외할 수 있는가?
8. `.msg` file도 Linux로 sync할 것인가, 아니면 Markdown과 선택한 attachment만 sync할 것인가?
9. Linux API는 `127.0.0.1`에만 bind할 것인가, 아니면 다른 machine에서 접근 가능해야 하는가?
10. MVP에서 HTML email body를 Markdown으로 변환할 것인가, 아니면 plain text로 충분한가?

## 25. MVP 기본 결정

별도 override가 없으면 다음 decision을 사용한다.

Outlook access:
- local Outlook COM automation을 사용한다.

Windows vault:
- `D:\KnowledgeVault`

Linux raw vault:
- `/home/kangsan/kb/KnowledgeVault-Raw`

Linux enriched vault:
- `/home/kangsan/kb/KnowledgeVault-Enriched`

Sync:
- SFTP over SSH.
- GitHub storage 사용 안 함.
- append/update sync 우선.
- MVP에서는 Linux file을 delete하지 않음.

Email format:
- email 하나당 Markdown file 하나.
- plain text body 저장.
- `.msg` original 저장.
- attachment 저장.

Index:
- SQLite FTS5.
- MVP에서는 embedding 사용 안 함.

API:
- FastAPI.
- `127.0.0.1`에 bind.
- bearer token required.

AI integration:
- Cline skill script가 API를 호출한다.
- read-only access only.

## 26. 완료 기준

다음이 모두 true이면 MVP가 complete이다.

1. 사용자가 Outlook folder 하나 이상을 configure할 수 있다.
2. Windows app이 해당 folder에서 email을 import할 수 있다.
3. imported email이 Windows Obsidian vault에 Markdown file로 나타난다.
4. configured이면 original `.msg` file과 attachment가 저장된다.
5. importer를 다시 실행해도 email이 duplicate되지 않는다.
6. Windows app은 GitHub 없이 vault file을 Linux로 sync할 수 있다.
7. Linux Cline CLI enrichment step은 raw Markdown을 overwrite하지 않고 enriched Markdown을 생성할 수 있다.
8. Linux app은 enriched vault를 index할 수 있다.
9. Linux API는 imported email을 search할 수 있다.
10. Linux API는 relative path로 note를 read할 수 있다.
11. API는 bearer token으로 보호된다.
12. Cline/Codex skill script가 API를 호출할 수 있다.
13. AI answer는 source path, sender, received date를 포함할 수 있다.
14. repository에는 real email, note, attachment, vault, database, secret data가 없다.
15. documentation은 system의 install, configure, run, troubleshoot 방법을 설명한다.

## 27. Codex 구현 지침

이 project를 implement할 때 다음 순서를 우선한다.

1. clean repository skeleton을 만든다.
2. testable pure function을 먼저 구현한다.
3. example config file 외에는 user-specific path를 hardcode하지 않는다.
4. real vault content 또는 real email data를 절대 commit하지 않는다.
5. Windows import와 Linux API를 separate package로 구현한다.
6. MVP에서 API는 read-only로 유지한다.
7. parsing, path safety, duplicate prevention test를 추가한다.
8. 명확한 setup instruction을 제공한다.
9. 작고 검증 가능한 milestone을 사용한다.
10. clever abstraction보다 boring하고 maintainable한 code를 선호한다.

Source repository를 vault data의 storage backend로 사용하지 않는다.
