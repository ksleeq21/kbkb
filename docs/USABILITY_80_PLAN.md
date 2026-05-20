# Usability 80 Plan

이 문서는 현재 MVP를 "기능 범위는 충분하지만 완성도는 60점"인 상태로 보고, 시니어 엔지니어 리뷰에서 "그럭저럭 쓸만하다"가 아니라 "MVP로는 충분히 탄탄하다"는 평가를 받을 수 있도록 80점까지 끌어올리는 실행 계획이다.

범위는 PRD의 로컬 우선, GitHub/GitHub Enterprise 저장 금지, 외부 SaaS 금지, read-only API 원칙을 유지한다. 기능을 크게 넓히기보다 사용자가 설치, 설정, 첫 성공, 문제 진단, 반복 운영을 덜 헷갈리게 만드는 데 집중한다.

## Target Score

현재 추정 점수: 60/100

목표 점수: 80/100

80점의 의미:

- 신규 사용자가 문서만 보고 30분 안에 synthetic fixture 기반 API 검색까지 성공한다.
- Windows 사용자가 Outlook import 전 단계에서 설정 오류를 명확히 확인할 수 있다.
- 실패 메시지가 "무엇이 잘못됐고, 다음에 무엇을 해야 하는지"를 알려준다.
- CLI가 dry-run, validate, reindex, smoke test 흐름을 자연스럽게 안내한다.
- 운영자는 로그와 상태 파일을 보고 import/sync/index 상태를 판단할 수 있다.
- Cline/Codex skill 사용자는 검색 결과의 출처와 신뢰도를 쉽게 인용할 수 있다.

## Review Feedback Summary

리뷰 피드백을 사용성 관점으로 재정리하면 다음과 같다.

- 기능은 PRD의 주요 범위를 덮지만, 첫 사용자 경험이 거칠다.
- 설정 파일을 직접 수정해야 하는데 어떤 값이 올바른지 즉시 검증하기 어렵다.
- Outlook, SFTP, API, skill이 분리되어 있어 첫 성공 경로가 길고 중간 상태 확인이 부족하다.
- 오류가 발생했을 때 로그와 문서를 왕복해야 한다.
- API와 skill은 동작하지만, 검색 결과 품질과 출처 표시가 사용자 친화적이지 않다.
- 실제 Windows/Outlook 환경에서 수동 검증해야 하는 항목과 로컬에서 자동 검증된 항목의 경계가 문서에서 더 선명해야 한다.

## Scoring Rubric

| Area | Current | Target | 판단 기준 |
| --- | ---: | ---: | --- |
| 설치/첫 실행 | 55 | 80 | README만 보고 fixture reindex/search 성공 |
| 설정 사용성 | 50 | 80 | `validate-config`가 누락/경로/토큰/폴더 문제를 명확히 보고 |
| Windows import UX | 55 | 75 | `--dry-run` 결과가 import 대상, skip 사유, 예상 파일 경로를 보여줌 |
| API UX | 65 | 80 | health/search/read/context/admin reindex가 일관된 JSON 오류와 예제를 제공 |
| Skill UX | 60 | 80 | 검색/읽기/context 결과가 출처, 날짜, sender, excerpt를 읽기 좋게 출력 |
| 운영/진단 | 55 | 80 | 상태, 로그, DB 통계를 한 명령으로 확인 |
| 테스트/회귀 | 70 | 85 | CLI, 보안, path traversal, unauthorized, fixture e2e 테스트가 자동화 |
| 문서 일치성 | 65 | 85 | 문서의 모든 명령이 실제 코드와 맞고 검증 범위가 명시됨 |

## Priority 0: Preserve MVP Boundaries

완성도 개선 중에도 아래는 변경하지 않는다.

- 외부 SaaS, Obsidian Sync, Obsidian Publish, Microsoft Graph API 의존성을 추가하지 않는다.
- Cline/Codex용 API는 read-only로 유지한다.
- 실제 이메일, 실제 첨부파일, 실제 vault 데이터는 저장소에 넣지 않는다.
- Windows Outlook 자동화는 classic Outlook desktop COM 기반 MVP로 유지한다.

## Priority 1: First-Run Experience

목표: 사용자가 코드를 받은 뒤 "설치가 됐는지"와 "API 검색이 되는지"를 가장 짧은 경로로 확인한다.

작업:

- `kb-api smoke-test --config examples/linux-config.fixture.yaml` 명령을 추가한다.
- smoke test가 fixture reindex, health, search, read, context 흐름을 한 번에 검증하게 한다.
- README 상단에 "5-minute local smoke test" 섹션을 추가한다.
- smoke test 성공 시 다음 단계로 Windows config 작성, API service 등록, skill 환경 변수 설정을 안내한다.
- 실패 시 exit code와 함께 실패 단계, 원인 후보, 다음 명령을 출력한다.

수용 기준:

- 신규 사용자가 실제 vault 없이 fixture만으로 검색 결과를 볼 수 있다.
- smoke test 출력에 DB path, indexed notes/chunks, sample query, sample source path가 포함된다.
- 실패 메시지에 Python 버전, config path, vault path 존재 여부가 포함된다.

## Priority 2: Config Validation and Guided Errors

목표: 설정 오류를 실제 import나 serve 실행 전에 잡는다.

작업:

- `kb-win-sync validate-config --config <path>`를 추가한다.
- `kb-api validate-config --config <path>`를 추가한다.
- Windows config 검증 항목:
  - required key 누락
  - vault/state/log parent path 해석 가능 여부
  - `outlook.folders` 비어 있음
  - folder별 `name`, `outlook_path`, `target_folder` 누락
  - sync enabled일 때 host, username, remote_path 누락
- Linux config 검증 항목:
  - vault path 존재 여부
  - database parent directory 생성 가능 여부
  - token env var 설정 여부
  - bind host가 `127.0.0.1`이 아닐 때 경고
- 오류 출력은 한 줄 traceback이 아니라 actionable checklist로 제공한다.

수용 기준:

- 잘못된 config fixture를 넣었을 때 누락 key가 모두 한 번에 보고된다.
- token 미설정은 serve 전 단계에서 명확한 경고로 표시된다.
- `validate-config`는 이메일 본문, token 값, SSH key 내용을 출력하지 않는다.

## Priority 3: Import Dry-Run UX

목표: Outlook import 전에 사용자가 무엇이 가져와질지, 무엇이 skip될지 이해한다.

작업:

- `--dry-run` 출력을 단순 path 목록에서 summary table로 개선한다.
- 각 메일에 대해 subject, sender, received, message_key, action(import/skip), reason, target_path를 표시한다.
- `--folder` 필터가 적용된 경우 선택된 folder와 제외된 folder 수를 표시한다.
- `--force` 사용 시 state skip이 무시된다는 경고를 표시한다.
- import 완료 후 summary를 출력한다: scanned, imported, skipped_duplicate, failed, attachments_saved, msg_saved.

수용 기준:

- 재실행 시 skip된 메일과 skip 사유가 보인다.
- `--dry-run`은 vault, state, attachment, `.msg` 파일을 쓰지 않는다.
- import 실패가 전체 실행을 중단하지 않고 summary에 누적된다.

## Priority 4: Attachment and `.msg` Completeness

목표: PRD상 중요하지만 현재 UX가 약한 원본 `.msg`와 첨부파일 저장 흐름을 완성도 있게 만든다.

작업:

- Outlook adapter에서 실제 attachment save와 `.msg` save hook을 구현한다.
- 저장된 attachment path와 original_msg path를 렌더링 전에 email model에 반영한다.
- attachment filename collision 처리 결과를 로그와 summary에 표시한다.
- 저장 실패 시 해당 attachment만 실패 처리하고 메일 Markdown은 생성한다.
- attachment 저장 관련 synthetic fake adapter 테스트를 추가한다.

수용 기준:

- `save_msg: true`일 때 `90_Attachments/email/<message-key>/original.msg`가 생성된다.
- `save_attachments: true`일 때 첨부파일이 deterministic path로 저장된다.
- Markdown frontmatter와 body link가 실제 저장 경로와 일치한다.

## Priority 5: API Response and Search UX

목표: AI 도구와 사람이 검색 결과를 더 쉽게 판단하게 한다.

작업:

- `/search` 응답에 `matched_fields`, `received`, `sender`, `tags`, `chunk_index`를 top-level로 추가한다.
- excerpt에서 검색어 주변 문맥을 우선 보여주는 highlight-friendly snippet을 만든다.
- 빈 query, limit 범위 초과, DB 미생성, FTS syntax 오류를 일관된 JSON 오류로 반환한다.
- `/health`를 기본 health와 `/health?deep=true`로 나눈다.
- deep health는 DB 존재 여부, notes count, last indexed time을 반환한다.

수용 기준:

- DB가 없을 때 500 traceback 대신 `database_not_indexed` 오류와 reindex 명령을 반환한다.
- 검색 결과만 보고도 출처 path, 제목, sender, received, type을 판단할 수 있다.
- 같은 fixture/query 결과가 반복 가능하다.

## Priority 6: Skill Script UX

목표: Cline/Codex가 검색 결과를 그대로 인용 가능한 evidence로 사용한다.

작업:

- `kb_search.py`에 `--json`, `--limit`, `--type`, `--tag`, `--sender`, `--folder`, `--after`, `--before` 옵션을 추가한다.
- `kb_context.py` 출력 형식을 "Evidence N" 블록으로 정리한다.
- API 연결 실패, token 누락, unauthorized, not found 오류를 사람이 읽기 좋은 메시지로 변환한다.
- 모든 스크립트가 stderr에는 진단, stdout에는 결과만 출력하도록 정리한다.

수용 기준:

- token 미설정 시 token 값을 출력하지 않고 환경 변수명만 안내한다.
- `--json` 출력은 다른 자동화에서 파싱 가능하다.
- evidence 출력에 path, title, type, sender, received, excerpt가 항상 포함된다.

## Priority 7: Observability and Status

목표: 운영자가 현재 상태를 한눈에 확인한다.

작업:

- `kb-win-sync status --config <path>`를 추가한다.
- Windows status 출력:
  - vault path 존재 여부
  - state file 존재 여부와 imported count
  - configured folders count
  - sync enabled 여부
  - last import time
- `kb-api status --config <path>`를 추가한다.
- API status 출력:
  - vault path 존재 여부
  - database path 존재 여부
  - notes/chunks count
  - newest indexed received date
  - token env var 존재 여부만 표시
- 로그 포맷에 run_id를 추가해 한 번의 실행을 추적 가능하게 한다.

수용 기준:

- status 명령은 민감값을 출력하지 않는다.
- 상태 파일이 손상된 경우 status가 명확히 실패하고 복구 방법을 안내한다.
- 운영 문서가 status 명령을 troubleshooting 첫 단계로 사용한다.

## Priority 8: Test Coverage for Usability Regressions

목표: 사용성 개선이 회귀하지 않도록 CLI와 오류 메시지를 테스트한다.

작업:

- `validate-config` 성공/실패 테스트를 추가한다.
- `smoke-test` 통합 테스트를 추가한다.
- unauthorized API, path traversal, empty query, DB missing 테스트를 보강한다.
- skill script의 token missing, unauthorized, JSON output 테스트를 추가한다.
- fake Outlook adapter로 dry-run/import summary 테스트를 추가한다.

수용 기준:

- `python3 -m unittest discover -s tests -v`가 네트워크와 실제 Outlook 없이 통과한다.
- 로컬 HTTP bind가 필요한 테스트는 명확히 분리되거나 샌드박스 제약을 문서화한다.
- fixture는 synthetic 데이터만 사용한다.

## Execution Order

1. First-run smoke test와 README quickstart를 먼저 만든다.
2. Config validation을 추가해 setup 실패를 앞에서 잡는다.
3. API/skill 오류 메시지와 출력 포맷을 정리한다.
4. Windows import dry-run summary와 status 명령을 추가한다.
5. `.msg`/attachment 저장 completeness를 fake adapter 테스트로 고정한다.
6. 운영 문서와 troubleshooting을 새 CLI 기준으로 갱신한다.
7. usability regression tests를 전체 suite에 포함한다.

## Definition of Done for 80점

- `README.md`의 quickstart 명령이 그대로 성공한다.
- `validate-config`, `status`, `smoke-test`가 Windows/API 각각의 첫 진단 경로가 된다.
- 실패 메시지가 traceback 중심이 아니라 사용자가 취할 다음 행동 중심이다.
- API non-health endpoint의 모든 인증 실패가 일관된 401 JSON을 반환한다.
- skill scripts가 source citation에 필요한 정보를 기본 출력한다.
- attachment와 `.msg` 저장 흐름이 fake adapter 테스트로 검증된다.
- 운영 문서가 실제 명령과 실제 오류 코드를 기준으로 업데이트된다.
- 모든 자동 테스트가 synthetic fixture만으로 통과한다.

## Out of Scope for 80점

- embedding 기반 RAG
- Outlook add-in
- Microsoft Graph API
- Obsidian plugin
- web UI dashboard
- 삭제 전파 sync
- 외부 SaaS 연동
- vault content Git 저장

## Suggested Milestones

## Implementation Progress

Started:

- `kb_api smoke-test`, `validate-config`, and `status` commands are implemented.
- `kb_win_sync validate-config` and `status` commands are implemented without requiring Outlook.
- `/health?deep=true` returns database/index status.
- `/search` results now expose sender, received, folder, tags, chunk index, and matched fields at top level.
- API error responses now use structured JSON for unauthorized, bad request, not found, database missing, and invalid query cases.
- Skill scripts now check `KB_API_TOKEN`, report API errors without printing token values, and `kb_search.py` supports `--json`, `--limit`, `--type`, `--tag`, `--sender`, `--folder`, `--after`, and `--before`.
- CLI usability regression tests cover smoke test, validation, status, and missing-token behavior.

Completed in current implementation:

- Editable install exposes concise `kb-api` and `kb-win-sync` console commands while preserving `python -m` fallback compatibility.
- `init-config`, `smoke-test`, `reindex`, and Windows import/dry-run success output now include explicit `next:` guidance.
- README, setup, workflow, operations, troubleshooting, and Windows setup docs now use the concise first-run commands.
- Skill script HTTP error formatting is shared by `kb_search.py` and `kb_context.py`, reducing duplicated parsing logic.
- CLI usability tests assert the console script declarations and guided `init-config` output.
- Full Outlook attachment and `.msg` save hooks with fake adapter tests.
- Manifest-backed incremental SFTP sync so unchanged files are not uploaded every run.
- Broader search filters: tag, after, and before, wired through `/search`, `/context`, and skill scripts.
- Search quality fallback reporting for FTS5 trigram support through `status`, `/health?deep=true`, and DB metadata.
- FastAPI optional deployment matches the stdlib server's structured error shape for explicit HTTP errors.

Remaining:

- Richer Windows import summary after actual Outlook integration testing.
- Highlight-friendly snippets around matched terms.
- Run-id logging across Windows import/sync.
- Optional JSON output for status commands if automation consumers need it.

### Milestone A: Setup Confidence

예상 효과: 60점에서 68점

- smoke-test
- validate-config
- README quickstart
- config 오류 테스트

### Milestone B: Runtime Confidence

예상 효과: 68점에서 75점

- status 명령
- dry-run/import summary
- API deep health
- DB missing/empty query 오류 개선
- `.msg`/attachment artifact save summary - implemented
- incremental sync manifest and retry-safe manifest writes - implemented

### Milestone C: AI Consumer Polish

예상 효과: 75점에서 80점

- skill script 옵션/JSON 출력
- context evidence 출력 개선
- search metadata 확장
- tag/date filters - implemented
- trigram support detection and fallback reporting - implemented
- 운영 문서와 regression tests 정리
