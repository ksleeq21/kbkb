# Troubleshooting

Start with the status command for the side that is failing.

Windows:

```powershell
python -m kb_win_sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Linux:

```bash
python3 -m kb_api status --config ~/.config/kb-api/config.yaml
python3 -m kb_api validate-config --config ~/.config/kb-api/config.yaml
```

## Symptom Matrix

| Symptom | Likely Cause | First Command | Fix |
| --- | --- | --- | --- |
| `KB_API_TOKEN is not set` | Skill shell has no token | `echo $KB_API_TOKEN` | Export `KB_API_TOKEN` in the same shell that runs the skill script |
| `/search` returns 401 | API and client token differ | `python3 -m kb_api status --config <config>` | Set the same `KB_API_TOKEN` for API process and skill shell |
| `/admin/reindex` returns 401 | Admin token missing or wrong | `echo $KB_API_ADMIN_TOKEN` | Set `KB_API_ADMIN_TOKEN` for the admin request |
| `database_not_indexed` | Reindex has not run or DB path changed | `python3 -m kb_api status --config <config>` | Run `python3 -m kb_api reindex --config <config>` |
| `/health` works but `/search` fails | Token, DB, or query issue | `curl -sS 'http://127.0.0.1:8765/health?deep=true'` | Verify DB exists and use a simple query |
| Empty search result | Vault not synced or not reindexed | `python3 -m kb_api status --config <config>` | Confirm Markdown files exist under vault path, then reindex |
| Path traversal rejected | Path is absolute or contains `..` | Check the requested path | Use vault-relative path such as `20_Emails/ProjectA/example.md` |
| Outlook unavailable | `pywin32`, classic Outlook, or session issue | `python -m kb_win_sync validate-config --config <config>` | Install Windows extras, use classic Outlook, run while logged in |
| Outlook folder not found | Wrong `outlook_path` | `python -m kb_win_sync --config <config> --dry-run` | Rebuild path from Outlook folder tree |
| Dry-run shows too many emails | Folder whitelist is too broad | Inspect `outlook.folders` | Use a dedicated `_KB` folder instead of Inbox |
| Duplicate emails skipped | State file already recorded message key | `python -m kb_win_sync status --config <config>` | This is expected; use `--force` only when intentional |
| SFTP connection failure | SSH key, username, host, or remote path issue | `ssh user@host` from Windows | Fix key, host, remote path, or permissions before enabling sync |
| Linux service starts but API unavailable | Service path/env mismatch | `journalctl --user -u kb-api.service -f` | Fix `WorkingDirectory`, `ExecStart`, or `EnvironmentFile` |
| Token value appears in logs | Unsafe wrapper or manual logging | Search local logs | Remove token echoing and rotate token |

## First Checks

Linux API:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

Windows import:

```powershell
python -m kb_win_sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
python -m kb_win_sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

Synthetic proof:

```bash
KB_API_TOKEN=test-token KB_API_ADMIN_TOKEN=admin-token python3 -m kb_api smoke-test --config examples/linux-config.fixture.yaml
```

## Safety Checks

Do not troubleshoot by committing local data. Before pushing code:

```bash
find . -name '.env' -o -name 'config.yaml' -o -name '*.sqlite' -o -name '*.msg'
```

The command should print nothing inside the source repository.
