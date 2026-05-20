# kbkb

Local-first Outlook-to-Obsidian knowledge base sync and read-only search API.

This repository is for source code only. Do not store Obsidian vault contents, exported emails, `.msg` files, attachments, SQLite databases, tokens, SSH keys, or personal notes in the source repository.

## Components

- `kb_win_sync`: Windows-side Outlook import, Markdown rendering, state storage, and optional SFTP sync.
- `kb_api`: Linux-side vault scanner, SQLite FTS indexer, and read-only HTTP API.
- `cline_skill_obsidian_kb`: Cline/Codex skill instructions and helper scripts.
- `examples`: synthetic configuration and service templates.

## Install

Core tests and indexing use only Python standard library.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

After editable install, use the short commands `kb-api` and `kb-win-sync`. The
legacy `python3 -m kb_api` and `python -m kb_win_sync` forms still work.

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
smoke-test: ok
next: kb-api init-config --output ~/.config/kb-api/config.yaml
```

Windows Outlook import requires optional packages on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
```

If you want to run with FastAPI/uvicorn later, install:

```bash
python3 -m pip install -e ".[api]"
```

The default MVP HTTP server uses the standard library and exposes the required read-only endpoints. `kb_api.fastapi_app:create_app` is available for deployments that install the optional FastAPI dependency.

For complete setup, token, service, upgrade, and uninstall instructions, see [docs/SETUP.md](docs/SETUP.md).

For a first-run usability checklist and remaining improvement ideas, see [docs/FIRST_RUN_UX_REVIEW.md](docs/FIRST_RUN_UX_REVIEW.md).

For common failure symptoms and first diagnostic commands, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

For Windows Outlook folder selection and Task Scheduler setup, see [docs/WINDOWS_OUTLOOK_SETUP.md](docs/WINDOWS_OUTLOOK_SETUP.md).

For the complete Windows install to Linux search workflow, see [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md).

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

The stable API/skill contract is documented in [docs/API_CONTRACT.md](docs/API_CONTRACT.md).

The Obsidian-native graph extension plan is documented in [docs/OBSIDIAN_GRAPH_DEVELOPMENT.md](docs/OBSIDIAN_GRAPH_DEVELOPMENT.md).

The end-to-end workflow documents the required raw Markdown -> Cline CLI enrichment -> enriched Markdown -> reindex sequence in [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md).

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

## Improvement Plan

The current MVP scope is sufficient, but the next quality target is usability. See `docs/USABILITY_80_PLAN.md` for the plan to move from a 60/100 review score to an 80/100 MVP.
