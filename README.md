# kbkb

Local-first Outlook-to-Obsidian knowledge base sync and read-only search API.

This repository is for source code only. Do not store Obsidian vault contents, exported emails, `.msg` files, attachments, SQLite databases, tokens, SSH keys, or personal notes in the source repository.

## Components

- `kb_win_sync`: Windows-side Outlook import, Markdown rendering, state storage, and optional SFTP sync.
- `kb_api`: Linux-side vault scanner, SQLite FTS indexer, and read-only HTTP API.
- `cline_skill_obsidian_kb`: Cline/Codex skill instructions and helper scripts.
- `examples`: synthetic configuration and service templates.

## Install Overview

Install the same source repository on both machines, but use different optional dependencies:

- Windows needs `.[windows]` for Outlook COM import and optional SFTP sync.
- Linux needs the core package for indexing/search. `.[api]` is optional and only needed for FastAPI/uvicorn deployments.

Keep local config, tokens, vault data, `.msg` files, attachments, logs, and SQLite databases outside the source repository.

Use [docs/SETUP.md](docs/SETUP.md) when you need the full token, service, upgrade, or uninstall procedure. The README below is the short install path.

## Windows Install

Run these commands in PowerShell from the repository root on the Windows machine that has classic Outlook installed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
kb-win-sync --help
```

Create the Windows importer config:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\kb-win-sync"
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Then discover Outlook folders and edit the generated config:

```powershell
kb-win-sync list-mailboxes
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Use [docs/WINDOWS_OUTLOOK_SETUP.md](docs/WINDOWS_OUTLOOK_SETUP.md) if Outlook folder paths, mailbox selection, or Task Scheduler setup are unclear. It is the Windows-only setup guide.

## Linux Install

Run these commands from the repository root on the Linux machine that will host the API and enriched vault:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
kb-api --help
```

Create the Linux API config outside the repository:

```bash
mkdir -p ~/.config/kb-api ~/.local/share/kb-api
kb-api init-config --output ~/.config/kb-api/config.yaml
```

Set local-only tokens in the shell that runs the API:

```bash
export KB_API_TOKEN='replace-with-local-token'
export KB_API_ADMIN_TOKEN='replace-with-admin-token'
```

Validate the config:

```bash
kb-api doctor --config ~/.config/kb-api/config.yaml
```

If you want to run with FastAPI/uvicorn instead of the default standard-library server, install the optional API dependency:

```bash
python -m pip install -e ".[api]"
```

Use [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md) when you are connecting Windows import, SFTP raw vault sync, Linux enrichment, reindex, and API search into one complete workflow.

## 5-Minute Local Smoke Test

This verifies the Linux API index/search/read path with synthetic fixture data only.

```bash
export KB_API_TOKEN='test-token'
export KB_API_ADMIN_TOKEN='admin-token'
kb-api smoke-test --config examples/linux-config.fixture.yaml
```

Expected output includes:

```text
validate-config: ok
reindex: ok notes=2 chunks=2
search: ok query=SSO source=20_Emails/ProjectA/2026-05-19_0915__Synthetic_SSO__abc123.md
read: ok title=Synthetic SSO incident analysis
context: ok evidence=1
smoke-test: ok
next: kb-api init-config --output ~/.config/kb-api/config.yaml
```

The default MVP HTTP server uses the standard library and exposes the required read-only endpoints. `kb_api.fastapi_app:create_app` is available for deployments that install the optional FastAPI dependency.

## Windows Import

1. Generate a local config at `%USERPROFILE%\kb-win-sync\config.yaml`.
2. Edit `vault_path`, whitelisted `outlook.folders`, and optional `sync`.
3. Run:

```powershell
kb-win-sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync list-mailboxes
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Only configured Outlook folders are scanned. Unconfigured folders are ignored.

Daily execution can use Windows Task Scheduler with `examples/run-kb-win-sync.bat`. Configure it to run only when the user is logged in if Outlook COM access requires an interactive desktop.

Use [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) if Outlook is unavailable, folders are not found, duplicate imports appear, or SFTP fails.

## Linux API

1. Generate a local config outside the repo.
2. Set local-only tokens:

```bash
export KB_API_TOKEN='replace-with-local-token'
export KB_API_ADMIN_TOKEN='replace-with-admin-token'
```

3. Enrich raw Markdown on Linux, then rebuild the index from the enriched Markdown vault:

```bash
kb-api init-config --output ~/.config/kb-api/config.yaml
kb-api doctor --config ~/.config/kb-api/config.yaml
kb-api enrich --config ~/.config/kb-api/config.yaml
kb-api reindex --config ~/.config/kb-api/config.yaml
kb-api status --config ~/.config/kb-api/config.yaml
```

4. Start the API:

```bash
kb-api serve --config ~/.config/kb-api/config.yaml
```

Endpoints:

- `GET /health`: unauthenticated health check.
- `GET /health?deep=true`: unauthenticated DB/index status check.
- `GET /search?q=...&limit=10`: bearer-token search.
- `GET /notes/by-path?path=...`: bearer-token read by vault-relative path.
- `POST /context`: bearer-token compact evidence bundle.
- `POST /admin/reindex`: admin-token reindex.

There are no create, update, or delete endpoints in the MVP.

Use [docs/API_CONTRACT.md](docs/API_CONTRACT.md) when changing API responses, skill scripts, auth headers, or endpoint paths. It defines the stable v1 contract.

Use [docs/OPERATIONS.md](docs/OPERATIONS.md) when setting up the service, daily operation, or reindex procedure after installation.

Use [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) if token auth, database status, search results, or service startup do not behave as expected.

## Cline/Codex Skill

Set:

```bash
export KB_API_BASE_URL=http://127.0.0.1:8765
export KB_API_TOKEN='replace-with-local-token'
```

Then use:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_search.py "SSO incident"
python3 cline_skill_obsidian_kb/scripts/kb_search.py "SSO incident" --limit 5 --json
python3 cline_skill_obsidian_kb/scripts/kb_read.py "20_Emails/ProjectA/example.md"
python3 cline_skill_obsidian_kb/scripts/kb_context.py "What did we decide about SSO rollback?"
```

## Security Notes

- Keep the API bound to `127.0.0.1` unless you have a reviewed network access plan.
- Use bearer tokens for every non-health endpoint.
- Use vault-relative paths only; absolute paths and `..` traversal are rejected.
- The repository test fixtures are synthetic and must remain synthetic.

Use [docs/SECURITY.md](docs/SECURITY.md) when reviewing storage boundaries, token handling, or whether a new sync/storage path is acceptable.

## Improvement Plan

Use [docs/PRD.md](docs/PRD.md) when deciding whether a feature belongs in scope. Use [docs/USABILITY_80_PLAN.md](docs/USABILITY_80_PLAN.md) and [docs/FIRST_RUN_UX_REVIEW.md](docs/FIRST_RUN_UX_REVIEW.md) when improving first-run UX or setup quality.

Use [docs/OBSIDIAN_GRAPH_DEVELOPMENT.md](docs/OBSIDIAN_GRAPH_DEVELOPMENT.md) only when working on graph search, backlinks, relationship tables, or future graph-boosted ranking.
