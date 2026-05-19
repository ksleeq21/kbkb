# Design

## Architecture

The system has three local-first parts:

1. Windows `kb_win_sync` reads explicitly configured Outlook folders through COM automation and writes Markdown into an Obsidian vault.
2. Optional SFTP sync copies vault files to a Linux vault copy. GitHub is not used as a sync backend.
3. Linux `kb_api` indexes Markdown files into SQLite FTS and exposes a read-only HTTP API for AI tools.

## Data Flow

```text
Outlook configured folders
  -> kb_win_sync
  -> Obsidian raw Markdown + attachments/.msg artifacts
  -> manifest-backed SFTP file copy
  -> Linux raw vault copy
  -> Cline CLI metadata enrichment
  -> Linux enriched vault copy
  -> kb_api reindex enriched vault
  -> SQLite notes/chunks/chunks_fts
  -> Cline/Codex skill scripts
```

## Windows Package

Important modules:

- `config.py`: parses the small YAML subset used by local config files.
- `state.py`: JSON import state with atomic replace on save.
- `render.py`: deterministic message keys, filename sanitization, target path generation, frontmatter, and Markdown rendering.
- `outlook.py`: optional `pywin32` COM adapter for Outlook LTSC desktop.
- `sync.py`: optional `paramiko` SFTP sync. The quality target is manifest-backed incremental upload after the first run.

The MVP duplicate key uses Internet Message-ID when present, otherwise a SHA-256 hash over conversation id, received time, sender, and subject.

Outlook artifact handling:

- `.msg` originals and regular attachments are saved under `90_Attachments/email/<message-key>/`.
- Artifact paths are vault-relative and are written into frontmatter before Markdown rendering.
- Artifact save failures are logged per item and do not stop the whole run unless the vault itself is unavailable.

## Linux Package

Important modules:

- `scanner.py`: recursively finds Markdown under the vault and ignores `.obsidian`, `.trash`, and `.git`.
- `frontmatter.py`: parses frontmatter without external dependencies.
- `enrichment.py`: turns raw Markdown plus validated Cline JSON metadata into separate enriched Markdown without modifying raw files.
- `indexer.py`: rebuilds SQLite tables and FTS rows from the enriched vault.
- `server.py`: standard-library HTTP API with bearer-token auth and path traversal defense.
- `fastapi_app.py`: optional FastAPI app factory for environments that install `.[api]`; it must preserve the same API contract and error shape as `server.py`.

SQLite schema:

- `notes(id, path, title, type, sender, received, folder, tags_json, metadata_json, body)`
- `chunks(id, note_id, chunk_index, text)`
- `chunks_fts(text, note_id, chunk_id)`

Search quality target:

- Prefer FTS5 trigram tokenizer when supported by the local SQLite build.
- Fall back to default FTS5 tokenizer with explicit diagnostic output when trigram is unavailable.
- Support type, tag, sender, folder, and date filters consistently across `/search`, `/context`, and skill scripts where applicable.

## API Contract

`/health` is public and returns `{"status":"ok"}`.

All other non-admin endpoints require `Authorization: Bearer $KB_API_TOKEN`.

`/admin/reindex` requires `Authorization: Bearer $KB_API_ADMIN_TOKEN`.

Read endpoints only return indexed vault content. They do not write to the vault.

## Security Decisions

- Personal knowledge data is excluded by `.gitignore`.
- The default bind address is `127.0.0.1`.
- Tokens are read from environment variables and are not logged.
- Skill scripts refuse empty read paths and never hardcode tokens.
- Path traversal is rejected before DB lookup.
- Tests use only synthetic fixture data.
