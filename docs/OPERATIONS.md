# 운영 가이드

첫 설정, token 생성, service 설치, upgrade, uninstall 절차는 `docs/SETUP.md`를 참고한다.
설치부터 검색까지의 전체 workflow는 `docs/END_TO_END_WORKFLOW.md`를 참고한다.

first-run UX gap과 계획된 개선사항은 `docs/FIRST_RUN_UX_REVIEW.md`를 참고한다.
Windows Outlook folder 선택과 Task Scheduler 세부사항은 `docs/WINDOWS_OUTLOOK_SETUP.md`를 참고한다.

## Windows 일일 Import

1. config를 `%USERPROFILE%\kb-win-sync\config.yaml`에 둔다.
2. Outlook folder path를 찾아야 하면 다음을 실행한다.

```powershell
kb-win-sync list-mailboxes --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

3. 다음 명령으로 config를 검증하고 status를 확인한다.

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync doctor --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

4. 다음 명령으로 미리 확인한다.

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

5. 실행한다.

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

6. Outlook import 없이 현재 Windows vault 파일만 Linux로 다시 업로드해야 하면 SFTP-only 명령을 실행한다.

```powershell
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --sync-only
```

7. Task Scheduler에서 `examples/run-kb-win-sync.bat`를 매일 실행한다. Outlook COM이 background session에서 시작되지 않으면 "Run only when user is logged on"을 선택한다.

## Linux Service 운영

`examples/kb-api.service`를 `~/.config/systemd/user/kb-api.service` 또는 `/etc/systemd/system/kb-api.service`로 복사한 뒤 path와 token을 수정한다.

```bash
systemctl --user daemon-reload
systemctl --user enable --now kb-api.service
systemctl --user status kb-api.service
journalctl --user -u kb-api.service -f
```

## Reindex

Linux Cline CLI enrichment 단계가 enriched Markdown vault를 만든 뒤 reindex를 실행한다. API config의 `vault_path`는 raw Windows sync directory가 아니라 enriched vault를 가리켜야 한다.

```bash
kb-api validate-config --config /path/to/linux-config.yaml
kb-api doctor --config /path/to/linux-config.yaml
kb-api enrich --config /path/to/linux-config.yaml
kb-api reindex --config /path/to/linux-config.yaml
kb-api status --config /path/to/linux-config.yaml
```

전체 vault 처리 전에 단일 raw Markdown만 검증하려면 raw vault 기준 상대 경로를 넘긴다.

```bash
kb-api enrich --config /path/to/linux-config.yaml --file "20_Emails/ProjectA/example.md"
```

또는 admin API를 사용한다.

```bash
curl -X POST http://127.0.0.1:8765/admin/reindex \
  -H "Authorization: Bearer $KB_API_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 문제 해결

더 자세한 증상 매트릭스는 `docs/TROUBLESHOOTING.md`를 참고한다.

- 첫 명령: Windows에서는 `kb-win-sync status --config <path>`, Linux에서는 `kb-api status --config <path>`를 실행한다.
- 첫 local API proof: `KB_API_TOKEN=test-token KB_API_ADMIN_TOKEN=admin-token kb-api smoke-test --config examples/linux-config.fixture.yaml`를 실행한다.
- Outlook unavailable: `pywin32`를 설치하고 classic Outlook desktop을 사용하며 interactive Windows session에서 실행한다.
- Folder missing: config의 전체 Outlook folder path를 확인하고 whitelisted folder만 유지한다.
- SFTP failure: host, username, key path, remote directory permission, `sync.enabled`가 의도된 값인지 확인한다.
- Vault path missing: local vault directory를 만들고 이 source repository 밖에 둔다.
- Token error: `KB_API_TOKEN` 또는 `KB_API_ADMIN_TOKEN`이 같은 shell 또는 service environment에 설정되어 있는지 확인한다.
- Path traversal rejected: absolute path나 `../` 대신 `20_Emails/ProjectA/example.md` 같은 vault-relative path를 사용한다.
