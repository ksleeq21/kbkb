아래는 그대로 PRD.md로 복사해서 Codex에 제공할 수 있는 문서입니다.

# PRD: Outlook-to-Obsidian Knowledge Base Sync & API

## 1. Product Summary

This project builds a local-first personal knowledge base pipeline for importing selected Microsoft Outlook emails and text notes into an Obsidian vault, synchronizing that vault from Windows to a Linux development environment, and exposing a read-only search API that can be used by Cline/Codex skills or other AI coding assistants.

The system is designed for an enterprise environment where personal knowledge files must not be stored in GitHub repositories, including the internal GitHub Enterprise instance at:

```text
https://github.sec.samsung.net

The internal GitHub Enterprise instance may be used only for source code repository management, not for backing up or storing personal emails, notes, or knowledge base contents.

2. Background

The user primarily performs document work and email communication on Windows using Microsoft Outlook included in:

Microsoft Office LTSC Professional Plus 2021

The user develops software on a separate Linux machine. Development is done from Windows by connecting to the Linux environment through VS Code Remote SSH. Cline and Codex are used in the Linux development environment.

The user wants to make past emails and personal text notes searchable and usable as a knowledge base. Obsidian is selected because it stores notes as local Markdown files in a vault folder, making it suitable for local-first knowledge management.

However, the source data and the AI execution environment are separated:

Windows:
- Microsoft Outlook
- Existing text notes
- Obsidian desktop
- Windows Obsidian vault

Linux:
- Development environment
- VS Code server
- Cline/Codex execution
- API server
- Synced copy of Obsidian vault

Because Cline runs in the Linux development environment and remote MCP access to local Windows data is not available, the preferred approach is to sync raw Markdown to Linux, enrich it on Linux with Cline CLI into a separate enriched vault, and expose a Linux-based HTTP API over the enriched vault. Cline can then use a skill or script to call the API.

3. Goals

3.1 Primary Goals

1. Import selected Outlook emails from Windows into an Obsidian vault as Markdown files.


2. Allow the user to configure which Outlook folders should be imported.


3. Preserve useful email metadata such as sender, recipients, subject, received time, Outlook folder, conversation ID, and attachments.


4. Save the original email as .msg when possible.


5. Save email attachments into the Obsidian vault in a deterministic folder structure.


6. Support manual import and scheduled daily import.


7. Synchronize the Windows Obsidian vault to a Linux vault copy without using GitHub as storage.


8. Build a Linux service that indexes the enriched vault and exposes a read-only HTTP API.


9. Allow Cline/Codex skills to search and read knowledge base content through the Linux API.


10. Keep the system local-first, enterprise-safe, and suitable for internal use.



3.2 Secondary Goals

1. Support existing text notes in the Obsidian vault.


2. Support project-based tagging and folder mapping.


3. Support keyword search over imported emails and notes.


4. Support date, sender, folder, tag, and type filters.


5. Support a context API that returns a compact evidence bundle for AI tools.


6. Make all components easy to run, debug, and extend.


7. Avoid unnecessary dependencies, paid services, SaaS services, or unclear license obligations.



4. Non-Goals

The project must not attempt to do the following in the first version:

1. Do not store Obsidian vault contents in GitHub or GitHub Enterprise.


2. Do not use https://github.sec.samsung.net as personal knowledge storage.


3. Do not upload emails, notes, or attachments to external SaaS services.


4. Do not depend on Obsidian Sync or Obsidian Publish.


5. Do not require Microsoft Graph API permissions in the MVP.


6. Do not require an Outlook add-in marketplace installation.


7. Do not expose the Windows Obsidian vault directly over the network.


8. Do not provide write/update/delete APIs to Cline in the first version.


9. Do not build a full RAG system with embeddings in the MVP.


10. Do not import every Outlook email by default.


11. Do not import sensitive folders unless explicitly configured by the user.


12. Do not assume that all attachments can be text-indexed in the MVP.



5. Users

5.1 Primary User

The primary user is a software engineer who:

Uses Windows for Outlook, documents, and general office work.

Uses Microsoft Office LTSC Professional Plus 2021.

Uses Obsidian to manage personal knowledge.

Uses Linux as the software development environment.

Uses VS Code Remote SSH from Windows to Linux.

Uses Cline/Codex in the Linux environment.

Wants AI tools to search past emails and notes when solving tasks.

Must follow enterprise restrictions against using GitHub as personal file storage.


5.2 AI Tool User

Cline/Codex acts as a secondary consumer of the knowledge base through the Linux API. It must be able to:

Search relevant historical emails and notes.

Read specific notes by path or ID.

Request a concise context bundle for a user question.

Cite source paths and email metadata when answering.


6. High-Level Architecture

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

7. Required Components

The product consists of two main applications and one lightweight AI integration package.

7.1 Component 1: kb-win-sync

A Windows application responsible for:

1. Reading Outlook emails from configured folders.


2. Writing imported emails into the Windows Obsidian vault.


3. Saving email metadata as YAML frontmatter.


4. Saving email body as Markdown.


5. Saving original .msg files.


6. Saving attachments.


7. Tracking already imported messages.


8. Synchronizing changed vault files to the Linux vault copy.


9. Supporting manual and scheduled execution.



7.2 Component 2: kb-api

A Linux application responsible for:

1. Reading the enriched Obsidian vault generated on Linux.


2. Parsing Markdown files and YAML frontmatter.


3. Indexing notes and email content into SQLite.


4. Providing full-text search.


5. Providing note read APIs.


6. Providing AI-friendly context APIs.


7. Running as a local service in the Linux development environment.


7.4 Component 4: Linux Cline CLI Enrichment

A Linux enrichment step responsible for:

1. Reading raw Markdown synced from Windows.


2. Calling Cline CLI with the raw Markdown as input.


3. Receiving structured metadata output such as tags, llm_tags, and llm_summary.


4. Validating the Cline CLI output.


5. Preserving the raw Markdown unchanged.


6. Writing a separate enriched Markdown file for indexing.


7. Supporting fixture-based tests using raw Markdown plus saved Cline output.



7.3 Component 3: cline-skill-obsidian-kb

A Cline/Codex skill package responsible for:

1. Explaining when the AI should use the knowledge base.


2. Providing scripts to call the Linux API.


3. Enforcing source citation behavior.


4. Preventing unsupported write operations.


5. Returning structured evidence to the AI assistant.



8. Functional Requirements

8.1 Windows App: kb-win-sync

FR-WIN-001: Configurable Outlook Folder Import

The app must allow the user to configure which Outlook folders should be imported.

Configuration must support:

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

Acceptance criteria:

The user can add or remove Outlook folders by editing a config file.

Only configured folders are imported.

Unconfigured folders are ignored.

Folder-specific tags are applied to imported Markdown files.

Folder-specific target paths are respected.


FR-WIN-002: Outlook LTSC 2021 Compatibility

The app must work with Microsoft Outlook included in Microsoft Office LTSC Professional Plus 2021.

Implementation expectation:

Use Outlook COM automation through PowerShell or Python pywin32.

Do not require Microsoft Graph API for MVP.

Do not require New Outlook.


Acceptance criteria:

The app can connect to the locally installed Outlook desktop client.

The app can enumerate configured folders.

The app can read MailItem objects.

The app can access subject, sender, recipients, received time, body, attachments, and conversation metadata where available.


FR-WIN-003: Email-to-Markdown Conversion

Each imported email must be saved as one Markdown file.

Recommended file path:

20_Emails/<FolderName>/<YYYY>/<MM>/<YYYY-MM-DD_HHMM>__<sanitized-subject>__<message-key>.md

Example:

20_Emails/ProjectA/2026/05/2026-05-19_0915__SSO장애원인분석__a1b2c3d4.md

Acceptance criteria:

One email creates one Markdown file.

File names are deterministic.

Unsafe file name characters are removed or replaced.

Long subjects are truncated safely.

Duplicate file names are avoided using a message key or hash.

Markdown files are readable in Obsidian.


FR-WIN-004: YAML Frontmatter

Each imported email Markdown file must include YAML frontmatter.

Required fields:

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

Acceptance criteria:

Frontmatter is valid YAML.

Missing fields are handled gracefully.

Timestamps use ISO-8601 format.

Attachment paths are relative to the vault root.

Original .msg path is relative to the vault root.

Tags are included from folder configuration.


FR-WIN-005: Email Body Formatting

The email body must be written below the frontmatter.

Recommended structure:

# <Email Subject>

## Metadata

- From: ...
- To: ...
- Cc: ...
- Received: ...
- Outlook folder: ...

## Body

<plain text email body>

## Attachments

- [[relative/path/to/attachment]]
- [[relative/path/to/original.msg]]

Acceptance criteria:

The body is readable in Obsidian.

Plain text body is preferred in MVP.

HTML-to-Markdown conversion is optional in MVP.

Basic whitespace cleanup is applied.

Attachments are linked from the Markdown file.


FR-WIN-006: Save Original .msg

When configured, the app must save the original email as a .msg file.

Recommended path:

90_Attachments/email/<message-key>/original.msg

Acceptance criteria:

Original .msg is saved when save_msg: true.

The saved file can be opened by Outlook.

The Markdown frontmatter includes the vault-relative original_msg path.

The Markdown Attachments section links the saved .msg path.

Failures to save .msg are logged but do not stop the entire import.

Implementation note:

The current config model exposes `save_msg`, but quality-complete behavior requires the Outlook adapter to pass through a save hook for the source MailItem and the importer to write the `.msg` artifact before rendering Markdown. Tests should use a fake Outlook item or fake artifact writer so this behavior is verified without requiring Outlook on CI.


FR-WIN-007: Save Attachments

When configured, the app must save email attachments.

Recommended path:

90_Attachments/email/<message-key>/<sanitized-attachment-name>

Acceptance criteria:

All regular attachments are saved when save_attachments: true.

Attachment file names are sanitized.

Duplicate attachment names are disambiguated.

Attachment paths are recorded in frontmatter.

Attachment paths are linked in the Markdown body.

Attachment and .msg counters in the import summary reflect actual saved artifacts.

Failures to save individual attachments are logged.

Implementation note:

The importer must save attachments before calling the Markdown renderer so `EmailAttachment.saved_path` is populated. Attachment save failures should be per-file failures, not run-level failures, unless the vault itself is not writable.


FR-WIN-008: Duplicate Import Prevention

The app must avoid importing the same email multiple times.

Duplicate detection should use a stable message key.

Preferred key priority:

1. Internet Message-ID, if available.


2. Conversation ID + received time + sender + subject hash.


3. Outlook EntryID hash as fallback.



Acceptance criteria:

Re-running the importer does not create duplicate Markdown files.

Imported message keys are stored in a local state file.

The state file survives across runs.

If an email already exists, the app skips it unless a force option is provided.


FR-WIN-009: Local State Management

The app must maintain local import state.

Recommended state path:

D:\kb-tools\state\outlook-import-state.json

State should include:

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

Acceptance criteria:

State is updated after successful import.

State is not corrupted if the process fails.

State writes are atomic where possible.

A backup of the previous state may be kept.


FR-WIN-010: Manual Trigger

The app must support manual execution.

Acceptance criteria:

The user can run the app from PowerShell.

The user can run the app from a .bat shortcut.

Logs are visible or written to a log file.

Exit code indicates success or failure.


Example:

powershell.exe -ExecutionPolicy Bypass -File D:\kb-tools\kb-win-sync.ps1

FR-WIN-011: Scheduled Execution

The app must support scheduled execution through Windows Task Scheduler.

Acceptance criteria:

The app can run unattended once per day.

The app can run without requiring interactive input.

The app logs scheduled run results.

The app handles Outlook not being open, if COM automation allows it.

If Outlook access fails, the app logs the error and exits cleanly.


FR-WIN-012: Windows-to-Linux Vault Sync

The app must sync the Windows vault to the Linux vault copy without using GitHub.

Recommended sync methods:

1. SFTP over SSH.


2. scp or sftp command-line tools.


3. rsync if available in the environment.


4. SMB mount if approved internally.



MVP recommendation:

SFTP over SSH with key-based authentication

Acceptance criteria:

New files are copied to Linux.

Changed files are copied to Linux.

Unchanged files are not repeatedly copied after the manifest feature is enabled.

Sync does not require GitHub.

Sync does not require external SaaS.

Sync errors are logged.

Sync can be disabled in config for testing.


FR-WIN-013: Incremental Sync Manifest

The app must maintain a sync manifest to avoid copying all files every time after the first successful sync.

Recommended manifest path:

D:\KnowledgeVault\.kb-sync-manifest.json

Manifest example:

{
  "20_Emails/ProjectA/2026/05/mail.md": {
    "size": 15342,
    "sha256": "abc...",
    "modified_at": "2026-05-19T09:30:00+09:00"
  }
}

Acceptance criteria:

The app calculates file hashes or reliable modified metadata.

The app identifies new and changed files.

The app uploads only new or changed files after the first manifest has been written.

The app stores the manifest safely.

The manifest write is atomic where possible.

If sync fails midway, the previous manifest is preserved and the next run retries unsynced files.

Quality note:

The implementation must connect `file_digest`, `load_manifest`, and `save_manifest` to `SftpSyncer.sync` so upload eligibility is decided by manifest diffing, not by a blind full-vault upload.


8.2 Linux App: kb-api

FR-LINUX-001: Vault Path Configuration

The Linux app must read a configured enriched vault path for indexing. Raw Markdown synced from Windows is read by the enrichment step, not directly by the indexer.

Example config:

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

Acceptance criteria:

Vault path is configurable.

Database path is configurable.

API host and port are configurable.

Secrets are read from environment variables, not hardcoded.


FR-LINUX-002: Markdown Scanner

The app must scan Markdown files under the vault.

Acceptance criteria:

The app finds .md files recursively.

The app ignores hidden/system folders unless configured otherwise.

The app can perform full reindex.

The app can perform incremental reindex based on file modification metadata if implemented.

The app handles malformed Markdown gracefully.


FR-LINUX-003: YAML Frontmatter Parser

The app must parse YAML frontmatter from notes.

Acceptance criteria:

The app extracts frontmatter if present.

The app handles files without frontmatter.

The app extracts fields such as type, subject, from, received, tags, and folder.

Invalid YAML is logged and does not crash the indexer.


FR-LINUX-004: SQLite Index

The app must index note metadata and content into SQLite.

Recommended tables:

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

Acceptance criteria:

Notes are stored with stable IDs.

Paths are unique.

Email metadata is queryable.

Content is searchable.

Reindex can rebuild the database from vault contents.

Search quality requirement:

The indexer should prefer FTS5 `trigram` when the local SQLite build supports it, because Korean compound words and partial strings are common in this knowledge base. If trigram is unavailable, the app must fall back to the default tokenizer and make that fallback visible in diagnostics or logs.


FR-LINUX-005: Full-Text Search API

The app must provide a search API.

Endpoint:

GET /search

Parameters:

q: required search query
limit: optional, default 10
type: optional, e.g. email, note
tag: optional
sender: optional
folder: optional
after: optional ISO date
before: optional ISO date

Example:

GET /search?q=SSO%20장애&type=email&tag=project/project-a&limit=10

Response example:

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

Acceptance criteria:

Search returns relevant notes.

Search result includes path, title, type, metadata, score, and excerpt.

Search supports filtering by type, tag, sender, folder, after, and before.

Type, tag, sender, folder, after, and before filters are implemented consistently in `/search`, `/context`, and skill scripts.

Search does not expose files outside the configured vault.


FR-LINUX-006: Note Read API

The app must provide an API to read a note.

Endpoint options:

GET /notes/{id}
GET /notes/by-path?path=<relative-path>

Acceptance criteria:

The API returns note metadata and body.

Path access is restricted to the configured vault.

Path traversal attempts are rejected.

Missing notes return 404.

The API does not modify notes.


FR-LINUX-007: Context API for AI Tools

The app must provide an AI-friendly context endpoint.

Endpoint:

POST /context

Request example:

{
  "query": "ProjectA SSO 장애 원인과 관련된 과거 메일을 찾아줘",
  "filters": {
    "type": "email",
    "tags": ["project/project-a"],
    "after": "2026-01-01"
  },
  "limit": 8
}

Response example:

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

Acceptance criteria:

The endpoint returns compact evidence suitable for Cline/Codex.

Each evidence item includes source path and metadata.

The response avoids returning too much text by default.

The response is deterministic enough for repeatable AI usage.


FR-LINUX-008: Reindex API

The app should provide an admin endpoint to reindex the vault.

Endpoint:

POST /admin/reindex

Acceptance criteria:

Reindex can be triggered manually.

Reindex rebuilds or updates the SQLite index.

Reindex requires authentication.

Reindex logs progress and errors.

Reindex does not modify vault files.


FR-LINUX-009: Authentication

The API must require a token for all non-health endpoints.

Recommended header:

Authorization: Bearer <KB_API_TOKEN>

Acceptance criteria:

/health may be unauthenticated.

/search, /notes, /context, and /admin/reindex require authentication.

Token is read from environment variable.

Invalid token returns 401 or 403.

Token is never logged.


FR-LINUX-010: Service Execution

The API should be runnable as a Linux service.

Acceptance criteria:

The app can run from the command line.

The app can run under systemd.

The app can be restarted.

Logs are written to stdout and/or a log file.

The app binds to 127.0.0.1 by default.


8.3 Cline/Codex Skill: cline-skill-obsidian-kb

FR-SKILL-001: Skill Package Structure

The skill package should be placed in a Cline-compatible skill directory.

Recommended structure:

.cline/
  skills/
    obsidian-kb/
      SKILL.md
      scripts/
        kb_search.py
        kb_context.py
        kb_read.py

Acceptance criteria:

Skill instructions are written in SKILL.md.

Scripts call the Linux API.

Scripts read API base URL and token from environment variables.

Scripts print JSON or readable text output for AI consumption.


FR-SKILL-002: Skill Behavior Instructions

SKILL.md must instruct the AI to use the KB API when the user asks about:

Past emails.

Previous decisions.

Project history.

Incidents.

Vendor/customer discussions.

Meeting notes.

Existing personal notes.

Any question requiring private historical context.


Acceptance criteria:

The skill tells the AI not to guess from memory.

The skill tells the AI to call the KB API first.

The skill tells the AI to cite source paths and metadata.

The skill tells the AI not to call unsupported write APIs.

The skill tells the AI to say when evidence is weak.


FR-SKILL-003: Search Script

The skill must include a search script.

Example usage:

python .cline/skills/obsidian-kb/scripts/kb_search.py "ProjectA SSO 장애"

Acceptance criteria:

The script calls GET /search.

The script supports query and optional limit.

The script passes the authorization token.

The script prints results clearly.


FR-SKILL-004: Context Script

The skill must include a context script.

Example usage:

python .cline/skills/obsidian-kb/scripts/kb_context.py "지난 3개월 ProjectA SSO 장애 관련 메일 요약"

Acceptance criteria:

The script calls POST /context.

The script supports query, limit, type, tag, sender, folder, after, and before filters.

The script prints source evidence.

The script is suitable for AI prompt consumption.


FR-SKILL-005: Read Script

The skill must include a note read script.

Example usage:

python .cline/skills/obsidian-kb/scripts/kb_read.py "20_Emails/ProjectA/2026/05/example.md"

Acceptance criteria:

The script calls GET /notes/by-path.

The script rejects empty paths.

The script prints note metadata and body.

The script does not modify files.


9. Data Model

9.1 Vault Structure

Recommended Windows vault path:

D:\KnowledgeVault

Recommended Linux vault path:

/home/kangsan/kb/KnowledgeVault

Recommended folder structure:

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

9.2 Email Markdown File

Example:

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

## Metadata

- From: Kim <kim@example.com>
- To: Hong <hong@example.com>
- Received: 2026-05-19 09:15
- Outlook folder: Inbox/_KB/ProjectA

## Body

메일 본문...

## Attachments

- [[90_Attachments/email/a1b2c3d4/report.xlsx]]
- [[90_Attachments/email/a1b2c3d4/original.msg]]

9.3 Config File

Recommended Windows config file:

D:\kb-tools\config.yaml

Example:

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

9.4 Linux API Config

Recommended Linux config file:

/home/kangsan/kb/kb-api.yaml

Example:

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

10. Security and Privacy Requirements

SEC-001: No GitHub Vault Storage

The system must not store email, notes, attachments, or vault contents in GitHub.

This applies to:

https://github.sec.samsung.net

The internal GitHub Enterprise instance may be used for source code only.

Acceptance criteria:

No vault data is committed to the source repository.

.gitignore prevents accidental vault/database/log inclusion.

Documentation warns that vault data must not be stored in GitHub.

Test fixtures must not contain real emails or sensitive notes.


SEC-002: Local-First Storage

All knowledge base data must remain on approved local Windows/Linux machines.

Acceptance criteria:

No external SaaS dependency.

No external API calls for email import.

No external LLM calls from the KB API.

No Obsidian Sync dependency.

No Obsidian Publish dependency.


SEC-003: Read-Only AI Access

The first version must expose only read-oriented APIs to Cline/Codex.

Acceptance criteria:

Cline/Codex can search and read.

Cline/Codex cannot create, update, or delete notes.

Admin reindex is authenticated.

Write APIs are not implemented in MVP.


SEC-004: API Token

The Linux API must use a bearer token.

Acceptance criteria:

Token is read from environment variable.

Token is required for non-health endpoints.

Token is not hardcoded.

Token is not logged.


SEC-005: Path Traversal Protection

The Linux API must prevent path traversal.

Acceptance criteria:

Requests using ../ are rejected.

Absolute paths are rejected unless explicitly allowed internally.

All note paths are resolved under the configured vault root.

Files outside the vault cannot be read.


SEC-006: Sensitive Data Controls

The importer must use a whitelist folder model.

Acceptance criteria:

Only configured Outlook folders are imported.

Importing all mailbox folders is not supported by default.

User must explicitly add folders to config.

Logs must not include full email bodies.

Logs should avoid excessive sensitive metadata.


11. Non-Functional Requirements

NFR-001: Simplicity

The MVP should be simple enough to run and debug manually.

Acceptance criteria:

Windows app can run from PowerShell.

Linux API can run from shell.

Config files are human-readable YAML.

Logs are human-readable.


NFR-002: Reliability

The system must handle partial failures safely.

Acceptance criteria:

Failure to import one email does not stop the entire run.

Failure to save one attachment is logged.

Failure to sync does not corrupt local vault.

State files are updated safely.

Re-running the app is idempotent.


NFR-003: Performance

The MVP should support a realistic personal knowledge base.

Target scale:

Emails: 10,000+
Markdown notes: 10,000+
Attachments: best effort, not all indexed

Acceptance criteria:

Importing a small daily batch should finish quickly.

Search should return within a few seconds.

Reindex should be acceptable for local use.

Incremental sync should avoid copying the entire vault every run where possible.


NFR-004: Portability

The project should avoid hardcoded user-specific values.

Acceptance criteria:

Paths are configurable.

Outlook folders are configurable.

API host/port are configurable.

Tokens are provided through environment variables.

Scripts work from documented commands.


NFR-005: Maintainability

The codebase should be easy for Codex/Cline to modify.

Acceptance criteria:

Clear module boundaries.

Clear README.

Tests for core functions.

No unnecessary framework complexity.

Type hints where Python is used.

Reasonable logging and error handling.


12. Recommended Repository Structure

The source code may be stored in internal GitHub Enterprise because it is code only. The vault data must not be stored in the repository.

Repository remote:

https://github.sec.samsung.net/<org>/<repo>

Recommended repository name:

obsidian-kb-pipeline

Recommended structure:

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

13. .gitignore Requirements

The repository must prevent accidental commit of real vault data, databases, logs, and secrets.

Required .gitignore entries:

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

14. MVP Scope

The MVP must deliver the minimum useful local-first workflow.

MVP Must Have

1. Windows config file.


2. Outlook folder whitelist.


3. Import one or more configured Outlook folders.


4. Convert emails to Markdown.


5. Save .msg original.


6. Save attachments.


7. Maintain import state to avoid duplicates.


8. Sync Windows vault files to Linux using SFTP.


9. Linux Cline CLI enrichment from raw Markdown to enriched Markdown.


10. Linux enriched vault scanner.


11. SQLite FTS index.


11. /health endpoint.


12. /search endpoint.


13. /notes/by-path endpoint.


14. Bearer token authentication.


15. Cline skill with kb_search.py and kb_read.py.


16. Documentation for setup and execution.



MVP Should Have

1. Incremental sync manifest.


2. /context endpoint.


3. POST /admin/reindex.


4. Windows Task Scheduler guide.


5. Linux systemd service file.


6. Basic tests.



MVP Can Defer

1. Embedding-based semantic search.


2. Graph-based note relationships.


3. Attachment text extraction.


4. HTML-to-Markdown high-fidelity conversion.


5. Outlook calendar import.


6. Two-way sync.


7. Note editing API.


8. MCP server wrapper.


9. Obsidian plugin development.



15. User Workflows

15.1 Manual Email Capture Workflow

1. User receives or finds an important Outlook email.
2. User moves or copies the email into a configured Outlook folder, e.g. Inbox/_KB/ProjectA.
3. User runs kb-win-sync manually.
4. kb-win-sync imports the email into the Windows Obsidian vault.
5. kb-win-sync syncs changed files to Linux.
6. Linux enrichment runs Cline CLI against the raw Markdown.
7. The enrichment step writes a separate enriched Markdown file.
8. kb-api indexes the enriched Markdown file.
9. User asks Cline/Codex about the topic.
10. Cline/Codex calls the KB API and uses the evidence.

15.2 Daily Automatic Import Workflow

1. User places useful emails into configured Outlook _KB folders during the day.
2. Windows Task Scheduler runs kb-win-sync once per day.
3. Emails are imported into the Windows Obsidian vault.
4. Changed files are synced to Linux.
5. Linux Cline CLI enrichment runs automatically or on demand.
6. Linux reindex runs against the enriched vault automatically or on demand.
7. Cline/Codex can search the updated knowledge base.

15.3 AI Search Workflow

Example user request:

지난 3개월 동안 ProjectA SSO 장애와 관련된 메일과 노트를 찾아서 원인, 결정사항, 남은 액션아이템을 정리해줘.

Expected AI behavior:

1. Cline/Codex detects that private historical knowledge is needed.
2. Cline/Codex uses the obsidian-kb skill.
3. Skill script calls kb-api /context or /search.
4. API returns relevant notes and emails.
5. AI reads high-value notes using /notes/by-path.
6. AI summarizes with evidence.
7. AI cites source path, sender, and received date where available.

16. API Specification

16.1 GET /health

Response:

{
  "status": "ok"
}

16.2 GET /search

Request:

GET /search?q=<query>&limit=10&type=email&tag=project/project-a
Authorization: Bearer <token>

Response:

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

16.3 GET /notes/by-path

Request:

GET /notes/by-path?path=20_Emails/ProjectA/2026/05/example.md
Authorization: Bearer <token>

Response:

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

16.4 POST /context

Request:

{
  "query": "ProjectA SSO 장애 원인",
  "filters": {
    "type": "email",
    "tags": ["project/project-a"]
  },
  "limit": 8
}

Response:

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

16.5 POST /admin/reindex

Request:

POST /admin/reindex
Authorization: Bearer <token>

Response:

{
  "status": "ok",
  "indexed_notes": 1234,
  "indexed_chunks": 4567
}

17. CLI Requirements

17.1 Windows CLI

Command:

kb-win-sync --config D:\kb-tools\config.yaml

Useful options:

--config <path>
--dry-run
--import-only
--sync-only
--folder <name>
--force
--verbose

Acceptance criteria:

--dry-run shows what would be imported.

--import-only skips sync.

--sync-only skips Outlook import.

--folder limits import to one configured folder.

--verbose increases logging.


17.2 Linux CLI

Commands:

kb-api reindex --config ~/kb/kb-api.yaml
kb-api serve --config ~/kb/kb-api.yaml

Acceptance criteria:

reindex indexes the vault.

serve starts the API server.

Both commands read the same config file.


18. Logging Requirements

Windows App Logs

The Windows app should log:

Run start and end.

Config path.

Number of configured folders.

Number of scanned emails.

Number of imported emails.

Number of skipped duplicates.

Number of saved attachments.

Number of sync uploads.

Errors and warnings.


The Windows app should not log:

Full email body.

Full attachment contents.

API tokens.

SSH private key contents.


Linux App Logs

The Linux app should log:

API server start.

Vault path.

Reindex start and end.

Number of indexed files.

Malformed frontmatter warnings.

Search errors.

Authentication failures without token values.


The Linux app should not log:

API token.

Full note contents by default.

Sensitive email bodies by default.


19. Error Handling Requirements

Windows App

The app must handle:

Outlook not available.

Config file missing.

Invalid Outlook folder path.

Email body read failure.

Attachment save failure.

.msg save failure.

Vault path missing.

SSH/SFTP connection failure.

Remote path missing.

State file corruption.


Expected behavior:

Log the error.

Continue when safe.

Exit with non-zero code for fatal errors.

Never corrupt the vault intentionally.

Never delete source Outlook emails.


Linux App

The app must handle:

Vault path missing.

SQLite open failure.

Invalid Markdown.

Invalid YAML frontmatter.

Path traversal attempts.

Missing note path.

Empty search query.

Invalid token.

Reindex failure.


Expected behavior:

Return appropriate HTTP status codes.

Log useful diagnostics.

Avoid exposing sensitive internals in API errors.


20. Testing Requirements

20.1 Unit Tests

Required tests:

kb_win_sync:
- filename sanitization
- message key generation
- Markdown rendering
- frontmatter generation
- state store read/write
- manifest diff logic

kb_api:
- frontmatter parsing
- vault path safety
- note indexing
- search query handling
- auth token handling
- note read by path

20.2 Integration Tests

Use fake test fixtures only. Do not include real emails.

Recommended fixtures:

tests/fixtures/vault/
  20_Emails/ProjectA/2026/05/sample-email.md
  10_Notes/sample-note.md

Required integration tests:

Index fixture vault.

Search returns expected fixture note.

Read-by-path returns expected note.

Path traversal is rejected.

Unauthorized request is rejected.


20.3 Manual Tests

Manual Windows test:

1. Create Outlook folder Inbox/_KB/General.
2. Copy one test email into the folder.
3. Run kb-win-sync.
4. Confirm Markdown file appears in Windows vault.
5. Confirm .msg file appears under 90_Attachments.
6. Confirm attachments are saved.
7. Run kb-win-sync again.
8. Confirm duplicate Markdown file is not created.

Manual Linux test:

1. Confirm raw vault exists on Linux.
2. Run Cline CLI enrichment.
3. Confirm enriched Markdown exists and raw Markdown is unchanged.
4. Run reindex against the enriched vault.
3. Start API server.
4. Call /health.
5. Call /search.
6. Call /notes/by-path.
7. Call script from Cline skill.

21. Documentation Requirements

The project must include:

1. README.md


2. PRD.md


3. DESIGN.md


4. PLAN.md


5. Windows setup guide.


6. Linux setup guide.


7. Cline skill setup guide.


8. Security notes.


9. Troubleshooting guide.



README must explain:

What this project does.

What this project does not do.

Why GitHub must not store vault data.

How to configure Outlook folders.

How to run Windows import.

How to sync to Linux.

How to run Linux API.

How to use the Cline skill.


22. Suggested Implementation Choices

Windows App

Preferred implementation:

Python + pywin32 + paramiko + pyyaml

Alternative:

PowerShell + Outlook COM + OpenSSH sftp

Recommendation:

Use Python if maintainability and testability are more important. Use PowerShell if the fastest possible Windows automation MVP is desired.

Linux App

Preferred implementation:

Python + FastAPI + SQLite FTS5 + pyyaml

Recommended packages:

fastapi
uvicorn
pydantic
pyyaml
python-frontmatter or custom parser

Sync

Preferred MVP:

SFTP over SSH

Avoid:

GitHub
External cloud drives
External SaaS sync services

23. Milestones

Milestone 1: Repository Skeleton

Deliverables:

Repository structure.

README.md.

PRD.md.

.gitignore.

Example config files.

Empty package skeletons.


Acceptance criteria:

Repository contains no real vault data.

Project can be opened by Codex/Cline.

Basic commands are documented.


Milestone 2: Windows Import MVP

Deliverables:

Config parser.

Outlook folder reader.

Markdown writer.

.msg saver.

Attachment saver.

State store.

Manual CLI.


Acceptance criteria:

One configured Outlook folder can be imported.

Re-run does not duplicate emails.

Markdown appears in Windows vault.

.msg and attachments are saved.


Milestone 3: Windows-to-Linux Sync MVP

Deliverables:

SFTP sync implementation.

Sync config.

Basic manifest or simple upload logic.

Sync logging.


Acceptance criteria:

Windows vault files are copied to the Linux raw vault.

Sync can run after import.

Sync failure is logged.


Milestone 3.5: Linux Cline CLI Enrichment MVP

Deliverables:

Raw Markdown input reader.

Cline CLI invocation wrapper.

Structured metadata output capture.

Metadata validator.

Enriched Markdown writer.

Golden fixture tests for raw Markdown plus Cline output.


Acceptance criteria:

Raw Markdown is never overwritten.

The same raw Markdown and saved Cline output generate the same enriched Markdown.

Invalid Cline output is rejected without modifying raw or enriched Markdown.

kb-api can index the enriched vault after enrichment succeeds.


Milestone 4: Linux Index and Search API

Deliverables:

Vault scanner.

Frontmatter parser.

SQLite schema.

Reindex command.

FastAPI server.

/health, /search, /notes/by-path.


Acceptance criteria:

Enriched vault can be indexed.

Search returns imported emails.

Note read works by path.

API requires bearer token.


Milestone 5: Cline Skill

Deliverables:

SKILL.md.

kb_search.py.

kb_read.py.

Optional kb_context.py.


Acceptance criteria:

Cline/Codex can call the scripts.

Scripts call the Linux API.

Results include source paths and metadata.

Skill instructions prevent unsupported write operations.


Milestone 6: Automation and Hardening

Deliverables:

Windows Task Scheduler guide.

Linux systemd service.

Admin reindex endpoint or timer.

Additional tests.

Troubleshooting guide.


Acceptance criteria:

Daily import can run automatically.

Linux API can run as a service.

System can recover from common failures.

Documentation is sufficient for repeat setup.


24. Open Questions

1. What is the exact Outlook mailbox display name on Windows?


2. What Outlook folders should be included in the first MVP?


3. What is the Windows vault path?


4. What is the Linux vault path?


5. Is SSH/SFTP from Windows to Linux allowed in the user's environment?


6. Should deleted files on Windows be deleted on Linux, or should sync be append/update only?


7. Should attachments be synced immediately, or can large attachments be excluded?


8. Should .msg files be synced to Linux, or only Markdown and selected attachments?


9. Should the Linux API bind only to 127.0.0.1, or be reachable from other machines?


10. Should HTML email bodies be converted to Markdown in MVP, or should plain text be enough?



25. Default Decisions for MVP

Unless overridden, use these decisions:

Outlook access:
- Use local Outlook COM automation.

Windows vault:
- D:\KnowledgeVault

Linux raw vault:
- /home/kangsan/kb/KnowledgeVault-Raw

Linux enriched vault:
- /home/kangsan/kb/KnowledgeVault-Enriched

Sync:
- SFTP over SSH.
- No GitHub storage.
- Append/update sync first.
- Do not delete Linux files in MVP.

Email format:
- One email per Markdown file.
- Save plain text body.
- Save .msg original.
- Save attachments.

Index:
- SQLite FTS5.
- No embeddings in MVP.

API:
- FastAPI.
- Bind to 127.0.0.1.
- Bearer token required.

AI integration:
- Cline skill scripts call the API.
- Read-only access only.

26. Definition of Done

The MVP is complete when all of the following are true:

1. The user can configure at least one Outlook folder.


2. The Windows app can import emails from that folder.


3. Imported emails appear as Markdown files in the Windows Obsidian vault.


4. Original .msg files and attachments are saved when configured.


5. Re-running the importer does not duplicate emails.


6. The Windows app can sync the vault files to Linux without using GitHub.


7. The Linux Cline CLI enrichment step can generate enriched Markdown without overwriting raw Markdown.


8. The Linux app can index the enriched vault.


9. The Linux API can search imported emails.


10. The Linux API can read a note by relative path.


10. The API is protected by a bearer token.


11. A Cline/Codex skill script can call the API.


12. AI answers can include source paths, sender, and received date.


13. The repository contains no real email, note, attachment, vault, database, or secret data.


14. Documentation explains how to install, configure, run, and troubleshoot the system.



27. Codex Implementation Instruction

When implementing this project, prioritize the following order:

1. Create a clean repository skeleton.


2. Implement testable pure functions first.


3. Avoid hardcoding user-specific paths except in example config files.


4. Never commit real vault contents or real email data.


5. Implement Windows import and Linux API as separate packages.


6. Keep APIs read-only in MVP.


7. Add tests for parsing, path safety, and duplicate prevention.


8. Provide clear setup instructions.


9. Use small, verifiable milestones.


10. Prefer boring, maintainable code over clever abstractions.



Do not use GitHub as a storage backend for vault data. The internal GitHub Enterprise instance at https://github.sec.samsung.net may be used only for the source code repository.
