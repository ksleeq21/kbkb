# Operations Guide

For first-time setup, token generation, service installation, upgrade, and uninstall steps, see `docs/SETUP.md`.
For the full install-to-search workflow, see `docs/END_TO_END_WORKFLOW.md`.

For first-run UX gaps and planned improvements, see `docs/FIRST_RUN_UX_REVIEW.md`.
For Windows Outlook folder selection and Task Scheduler details, see `docs/WINDOWS_OUTLOOK_SETUP.md`.

## Windows Daily Import

1. Put config at `%USERPROFILE%\kb-win-sync\config.yaml`.
2. If you need to discover Outlook folder paths, run:

```powershell
python -m kb_win_sync list-mailboxes
```

3. Validate and inspect status with:

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

4. Preview with:

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

5. Run:

```powershell
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

6. In Task Scheduler, run `examples/run-kb-win-sync.bat` daily. If Outlook COM cannot start in a background session, select "Run only when user is logged on".

## Linux Service

Copy `examples/kb-api.service` to `~/.config/systemd/user/kb-api.service` or `/etc/systemd/system/kb-api.service`, then edit paths and tokens.

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-api.service
systemctl --user status kb-api.service
journalctl --user -u kb-api.service -f
```

## Reindex

Run reindex after the Linux Cline CLI enrichment step has generated the enriched Markdown vault. The API config `vault_path` should point at the enriched vault, not the raw Windows sync directory.

```bash
python3 -m kb_api validate-config --config /path/to/linux-config.yaml
python3 -m kb_api doctor --config /path/to/linux-config.yaml
python3 -m kb_api enrich --config /path/to/linux-config.yaml
python3 -m kb_api reindex --config /path/to/linux-config.yaml
python3 -m kb_api status --config /path/to/linux-config.yaml
```

Or through the admin API:

```bash
curl -X POST http://127.0.0.1:8765/admin/reindex \
  -H "Authorization: Bearer $KB_API_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Troubleshooting

For a fuller symptom matrix, see `docs/TROUBLESHOOTING.md`.

- First command: run `python -m kb_win_sync status --config <path>` on Windows or `python3 -m kb_api status --config <path>` on Linux.
- First local API proof: run `KB_API_TOKEN=test-token KB_API_ADMIN_TOKEN=admin-token python3 -m kb_api smoke-test --config examples/linux-config.fixture.yaml`.
- Outlook unavailable: install `pywin32`, use classic Outlook desktop, and run in an interactive Windows session.
- Folder missing: verify the full Outlook folder path in the config and keep only whitelisted folders.
- SFTP failure: check host, username, key path, remote directory permissions, and that `sync.enabled` is intentional.
- Vault path missing: create the local vault directory and keep it outside this source repository.
- Token error: confirm `KB_API_TOKEN` or `KB_API_ADMIN_TOKEN` is set in the same shell or service environment.
- Path traversal rejected: use vault-relative paths such as `20_Emails/ProjectA/example.md`, not absolute paths or `../`.
