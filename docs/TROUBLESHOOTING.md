# 문제 해결

문제가 발생한 쪽의 status command부터 실행한다.

Windows:

```powershell
kb-win-sync status --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
```

Linux:

```bash
kb-api status --config ~/.config/kb-api/config.yaml
kb-api validate-config --config ~/.config/kb-api/config.yaml
```

## 증상 매트릭스

| 증상 | 가능성 높은 원인 | 첫 명령 | 해결 |
| --- | --- | --- | --- |
| `KB_API_TOKEN is not set` | skill을 실행하는 shell에 token이 없음 | `echo $KB_API_TOKEN` | skill script를 실행하는 같은 shell에서 `KB_API_TOKEN`을 export한다 |
| `/search`가 401을 반환함 | API와 client token이 다름 | `kb-api status --config <config>` | API process와 skill shell에 같은 `KB_API_TOKEN`을 설정한다 |
| `/admin/reindex`가 401을 반환함 | admin token이 없거나 틀림 | `echo $KB_API_ADMIN_TOKEN` | admin request용 `KB_API_ADMIN_TOKEN`을 설정한다 |
| `database_not_indexed` | reindex가 실행되지 않았거나 DB path가 바뀜 | `kb-api status --config <config>` | `kb-api reindex --config <config>`를 실행한다 |
| `/health`는 동작하지만 `/search`가 실패함 | token, DB, query 문제 | `curl -sS 'http://127.0.0.1:8765/health?deep=true'` | DB가 존재하는지 확인하고 단순 query를 사용한다 |
| 검색 결과가 비어 있음 | vault가 sync되지 않았거나 reindex되지 않음 | `kb-api status --config <config>` | vault path 아래 Markdown 파일이 있는지 확인한 뒤 reindex한다 |
| path traversal이 거부됨 | path가 absolute이거나 `..`를 포함함 | 요청한 path 확인 | `20_Emails/ProjectA/example.md` 같은 vault-relative path를 사용한다 |
| Outlook을 사용할 수 없음 | `pywin32`, classic Outlook, session 문제 | `kb-win-sync validate-config --config <config>` | Windows extras를 설치하고 classic Outlook을 사용하며 로그인된 상태에서 실행한다 |
| Outlook folder를 찾을 수 없음 | `outlook_path`가 틀림 | `kb-win-sync --config <config> --dry-run` | Outlook folder tree에서 path를 다시 만든다 |
| 실제 import가 멈춘 것처럼 보임 | Outlook COM scan, 큰 mailbox, attachment 저장, SFTP 대기 | 콘솔 INFO 또는 config의 `log_path` 확인 | `--verbose`로 재실행하고 마지막 folder/message 로그를 기준으로 원인을 좁힌다 |
| dry-run에 너무 많은 email이 보임 | folder whitelist가 너무 넓음 | `outlook.folders` 확인 | Inbox 대신 전용 `_KB` folder를 사용한다 |
| 중복 email이 skip됨 | state file에 message key가 이미 기록됨 | `kb-win-sync status --config <config>` | 정상 동작이다. 의도한 경우에만 `--force`를 사용한다 |
| SFTP 연결 실패 | SSH key, username, host, remote path 문제 | Windows에서 `ssh user@host` | sync를 켜기 전에 key, host, remote path, permission을 고친다 |
| Linux service는 시작되지만 API에 접근할 수 없음 | service path/env 불일치 | `journalctl --user -u kb-api.service -f` | `WorkingDirectory`, `ExecStart`, `EnvironmentFile`을 고친다 |
| token 값이 log에 나타남 | 안전하지 않은 wrapper 또는 수동 logging | local log 검색 | token echo를 제거하고 token을 교체한다 |

## 첫 확인

Linux API:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

Windows import:

```powershell
kb-win-sync validate-config --config "$env:USERPROFILE\kb-win-sync\config.yaml"
kb-win-sync --config "$env:USERPROFILE\kb-win-sync\config.yaml" --dry-run
```

Synthetic proof:

```bash
KB_API_TOKEN=test-token KB_API_ADMIN_TOKEN=admin-token kb-api smoke-test --config examples/linux-config.fixture.yaml
```

## 안전 확인

local data를 커밋하면서 문제를 해결하려 하지 않는다. code를 push하기 전에 다음을 실행한다.

```bash
find . -name '.env' -o -name 'config.yaml' -o -name '*.sqlite' -o -name '*.msg'
```

이 명령은 source repository 안에서 아무것도 출력하지 않아야 한다.
