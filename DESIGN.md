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
  -> Obsidian Markdown + optional attachments/.msg
  -> SFTP file copy
  -> Linux vault copy
  -> kb_api reindex
  -> SQLite notes/chunks/chunks_fts
  -> Cline/Codex skill scripts
```

## Windows Package

Important modules:

- `config.py`: parses the small YAML subset used by local config files.
- `state.py`: JSON import state with atomic replace on save.
- `render.py`: deterministic message keys, filename sanitization, target path generation, frontmatter, and Markdown rendering.
- `outlook.py`: optional `pywin32` COM adapter for Outlook LTSC desktop.
- `sync.py`: optional `paramiko` SFTP full-sync implementation.

The MVP duplicate key uses Internet Message-ID when present, otherwise a SHA-256 hash over conversation id, received time, sender, and subject.

## Linux Package

Important modules:

- `scanner.py`: recursively finds Markdown under the vault and ignores `.obsidian`, `.trash`, and `.git`.
- `frontmatter.py`: parses frontmatter without external dependencies.
- `indexer.py`: rebuilds SQLite tables and FTS rows.
- `server.py`: standard-library HTTP API with bearer-token auth and path traversal defense.
- `fastapi_app.py`: optional FastAPI app factory for environments that install `.[api]`.

SQLite schema:

- `notes(id, path, title, type, sender, received, folder, tags_json, metadata_json, body)`
- `chunks(id, note_id, chunk_index, text)`
- `chunks_fts(text, note_id, chunk_id)`

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
