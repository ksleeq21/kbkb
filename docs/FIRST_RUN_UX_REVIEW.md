# First-Run UX Review

이 문서는 최초 설치, 첫 실행, 스케줄 등록까지의 사용성을 다시 검토한 결과와 추가 개선 후보를 정리한다. 현재 구현은 MVP 기능 검증에는 충분하지만, Windows Outlook, Linux API, Cline/Codex skill이 나뉘어 있어 처음 설치하는 사용자가 흐름을 놓치기 쉽다.

## Current UX Assessment

현재 좋은 점:

- synthetic fixture 기반 `smoke-test`가 있어 실제 이메일 없이 API 검색 흐름을 검증할 수 있다.
- `validate-config`와 `status`가 있어 실행 전 설정 오류를 일부 확인할 수 있다.
- KB API token, admin token, SFTP key 위치가 문서화되어 있다.
- `docs/API_CONTRACT.md`로 skill/API 계약이 고정되어 있다.
- Windows config, Linux config, systemd service, `.bat` 예제가 있다.

현재 부족한 점:

- 사용자가 "Windows에서 해야 할 일"과 "Linux에서 해야 할 일"을 한눈에 보기 어렵다.
- README quickstart가 Linux API 중심이고 Windows Outlook import까지의 end-to-end 성공 기준은 약하다.
- Task Scheduler 등록은 권장 설정만 있고 단계별 GUI 절차나 `schtasks` 예제가 없다.
- Outlook folder path를 찾고 검증하는 절차가 별도 문서로 분리되어 있지 않다.
- SFTP sync를 켜기 전 SSH 연결을 독립적으로 검증하는 절차가 부족하다.
- service 설치 후 API가 실제로 응답하는지 확인하는 curl 예제가 부족하다.
- config 생성이 수동 copy/edit 중심이라 오타 가능성이 높다.
- 실패 시 "어느 로그를 먼저 볼지"는 있지만, 증상별 복구 순서가 더 구체적일 수 있다.

## Suggested Additions

### 1. Role-Based First-Run Map

문서에 다음 두 경로를 명확히 분리한다.

- Windows path: Outlook folder 선택, config 작성, dry-run, import, Task Scheduler
- Linux path: token 생성, config 작성, reindex, serve/systemd, skill script

추가 위치:

- `README.md` 상단
- `docs/SETUP.md`

수용 기준:

- 사용자가 "지금 Windows에서 할 일"과 "지금 Linux에서 할 일"을 1분 안에 구분할 수 있다.

### 2. End-to-End First Run Checklist

추가할 체크리스트:

1. Linux에서 fixture smoke test 성공
2. Linux config validate 성공
3. Linux API serve 실행
4. `/health`와 `/health?deep=true` curl 성공
5. Windows config validate 성공
6. Windows dry-run에서 가져올 메일 확인
7. Windows import 실행
8. Linux raw vault에 Markdown 도착
9. Linux Cline CLI enrichment 실행
10. Linux enriched vault reindex 실행
11. skill script search 성공

추가 위치:

- `docs/SETUP.md`
- `docs/OPERATIONS.md`

수용 기준:

- 각 단계마다 성공 기준이 한 줄로 있다.
- 실패 시 다음 진단 명령이 함께 있다.

### 3. Outlook Folder Selection Guide

추가 내용:

- classic Outlook 왼쪽 folder tree에서 최상위 mailbox 이름 확인
- `\\Mailbox - User\\Inbox\\_KB\\ProjectA` 형식 설명
- 공유 mailbox 예시
- Inbox 전체 대신 `_KB` 전용 폴더 권장
- 민감 폴더는 config에 넣지 않는 원칙
- folder path가 틀렸을 때 나타나는 증상과 수정 방법

추가 위치:

- `docs/WINDOWS_OUTLOOK_SETUP.md`
- README의 Windows Import 섹션에서 링크

수용 기준:

- Outlook을 모르는 사용자도 config의 `outlook_path`를 작성할 수 있다.

### 4. Windows Task Scheduler Step-by-Step

현재 문서는 "Task Scheduler 사용" 수준이다. 다음이 필요하다.

- GUI 절차:
  - Create Task
  - General: Run only when user is logged on
  - Triggers: daily
  - Actions: `examples/run-kb-win-sync.bat`
  - Start in: repository or installed package directory
  - Conditions/Settings 권장값
- `schtasks` CLI 예제
- 로그 리다이렉션 wrapper 예제
- 스케줄 비활성화/삭제 절차

추가 위치:

- `docs/WINDOWS_OUTLOOK_SETUP.md`
- `docs/SETUP.md`에서 링크

수용 기준:

- 사용자가 Task Scheduler UI를 열고 그대로 등록할 수 있다.

### 5. SFTP Sync Preflight

추가 내용:

- Windows PowerShell에서 SSH 접속 확인
- remote path 생성/권한 확인
- sync disabled 상태와 enabled 상태의 차이
- GitHub를 sync backend로 사용하지 않는다는 재확인
- SFTP 실패 시 import state/vault를 손상시키지 않는 기대 동작

추가 위치:

- `docs/SETUP.md`
- `docs/OPERATIONS.md`

수용 기준:

- sync를 켜기 전에 SSH 문제를 독립적으로 잡을 수 있다.

### 6. Linux Service Verification

추가할 명령:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS 'http://127.0.0.1:8765/health?deep=true'
curl -sS 'http://127.0.0.1:8765/search?q=SSO' -H "Authorization: Bearer $KB_API_TOKEN"
```

추가 위치:

- `docs/SETUP.md`
- `docs/OPERATIONS.md`

수용 기준:

- systemd가 떠 있어도 API가 실제로 검색 가능한지 확인할 수 있다.

### 7. Config Bootstrap Commands

현재는 예제 config를 복사하고 직접 편집한다. 개선 후보:

- `python3 -m kb_api init-config --output ~/.config/kb-api/config.yaml`
- `python -m kb_win_sync init-config --output "$env:USERPROFILE\kb-win-sync\config.yaml"`
- overwrite 방지
- 생성 후 다음 명령 안내

추가 위치:

- 구현 후보로 `docs/USABILITY_80_PLAN.md`에 추가

수용 기준:

- 사용자가 예제 파일 경로를 외우지 않아도 첫 config를 만들 수 있다.

### 8. Guided Setup Doctor

개선 후보:

- `python3 -m kb_api doctor --config <path>`
- `python -m kb_win_sync doctor --config <path>`

`doctor`는 `validate-config`, `status`, dependency check, token env check, path check를 한 번에 실행한다.

추가 위치:

- `docs/USABILITY_80_PLAN.md`

수용 기준:

- "안 된다" 상황에서 첫 진단 명령이 하나로 통일된다.

### 9. Clear Success Screens

개선 후보:

- `smoke-test` 성공 시 다음 명령을 출력한다.
- Windows import 성공 시 "created Markdown files", "skipped duplicates", "next reindex command"를 출력한다.
- API reindex 성공 시 "try this search command"를 출력한다.

추가 위치:

- 구현 후보로 `docs/USABILITY_80_PLAN.md`

수용 기준:

- 각 단계가 끝났을 때 사용자가 다음 행동을 알 수 있다.

### 10. One-Page Troubleshooting Matrix

추가할 matrix:

| Symptom | Likely Cause | First Command | Fix |
| --- | --- | --- | --- |
| `KB_API_TOKEN is not set` | env var missing | `echo $KB_API_TOKEN` | export token or systemd env file |
| `/search` 401 | wrong token | `python3 -m kb_api status` | set same token for API and skill |
| DB missing | reindex not run | `python3 -m kb_api status` | run reindex |
| Outlook unavailable | pywin32/classic Outlook/session issue | `python -m kb_win_sync validate-config` | install deps, use classic Outlook |
| folder not found | wrong `outlook_path` | dry-run | fix path from Outlook tree |
| SFTP failure | SSH/key/remote path issue | `ssh user@host` | fix key/path/permissions |

추가 위치:

- `docs/TROUBLESHOOTING.md`
- `docs/OPERATIONS.md`에서 링크

수용 기준:

- 흔한 장애에서 문서를 뒤지지 않고 첫 명령과 조치가 보인다.

## Prioritized Implementation List

### P0: Documentation Only, Immediate

- Add `docs/WINDOWS_OUTLOOK_SETUP.md`. Implemented.
- Add `docs/TROUBLESHOOTING.md`. Implemented.
- Add end-to-end checklist to `docs/SETUP.md`. Implemented as `First-Run Path`.
- Add curl verification commands for Linux service. Implemented.
- Add SFTP preflight section. Implemented.
- Link all first-run docs from README. Implemented.

### P1: Small CLI Improvements

- Add `init-config` for `kb_api`. Implemented.
- Add `init-config` for `kb_win_sync`. Implemented.
- Add `doctor` alias that runs validate/status and prints next actions. Implemented.
- Improve success output for `smoke-test`, `reindex`, and Windows import.

### P2: Deeper UX Improvements

- Add Outlook folder discovery helper on Windows if COM access can enumerate folders safely.
- Add `--json` output to status commands for automation.
- Add `kb_api serve --print-token-status` or startup banner that confirms token env var presence without printing token values.
- Add service install helper that writes a user systemd file from a template.

## Recommended Next Step

Implement P0 documentation first. It has the highest usability impact with the lowest risk. Then implement P1 CLI helpers once the desired first-run flow is stable.
