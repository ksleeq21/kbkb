# 계획: Outlook-to-Obsidian Knowledge Base Sync & API

이 계획은 `docs/PRD.md`를 기준으로 MVP를 스토리 단위로 쪼갠 실행 계획이다. 각 스토리는 독립적으로 완료 여부를 판단할 수 있어야 하며, 실제 이메일/노트/첨부파일/볼트 데이터는 저장소에 포함하지 않는다.

## Story 1: 저장소 골격과 안전장치 구성

- [x] 완료

### 목표

소스 코드만 저장하는 저장소 구조를 만들고, Obsidian vault 데이터와 런타임 산출물이 Git에 들어가지 않도록 기본 안전장치를 마련한다.

### 작업

- 권장 구조에 맞춰 `kb_win_sync/`, `kb_api/`, `cline_skill_obsidian_kb/`, `examples/`, `docs/` 디렉터리를 만든다.
- 루트 `README.md`, `DESIGN.md`, `.gitignore` 초안을 만든다.
- Windows/Linux 예제 설정 파일을 `examples/` 아래에 추가한다.
- 실제 vault, `.msg`, 첨부파일, SQLite DB, 로그, 상태 파일, 비밀키, 로컬 config가 무시되도록 `.gitignore`를 구성한다.

### 검증 조건

- `find` 또는 동등한 명령으로 권장 디렉터리 구조가 존재함을 확인한다.
- `.gitignore`에 `KnowledgeVault/`, `vault/`, `90_Attachments/`, `*.msg`, `*.sqlite`, `.env`, `config.yaml`, 로그/상태 디렉터리가 포함되어 있다.
- 저장소 안에 실제 이메일, 실제 첨부파일, 실제 vault 데이터, 실제 토큰 또는 SSH 키가 없다.
- README에 저장소에 실제 이메일, 첨부파일, vault 데이터, 토큰 또는 SSH 키를 저장하지 않는다는 경고가 포함되어 있다.

## Story 2: Windows 설정, 로깅, 상태 저장 기반 구현

- [x] 완료

### 목표

`kb-win-sync`가 Outlook 가져오기와 동기화를 수행하기 전에 필요한 설정 파싱, 로깅, 상태 파일 관리를 안정적으로 제공한다.

### 작업

- Python 패키지 골격과 CLI 진입점을 만든다.
- YAML 설정 파서를 구현한다.
- Windows vault 경로, Outlook 폴더 whitelist, 상태 파일, 로그 파일, sync 설정을 모델링한다.
- import state를 JSON으로 읽고 쓰는 저장소를 구현한다.
- 상태 파일 저장은 가능한 원자적으로 처리하고 기존 상태 손상에 대비한다.
- 기본 로그 포맷을 구성하고 이메일 본문, 토큰, 키 내용은 로그에 남기지 않는다.

### 검증 조건

- 예제 Windows config를 파싱할 수 있다.
- 필수 설정이 누락되면 명확한 오류가 발생한다.
- 상태 파일이 없으면 빈 상태로 시작한다.
- 상태 파일 저장 후 다시 읽으면 imported message 정보가 보존된다.
- 손상된 상태 파일 입력에 대해 프로세스가 조용히 오동작하지 않고 오류를 보고한다.
- 단위 테스트가 config 파싱과 state read/write를 검증한다.

## Story 3: 이메일 파일명, 메시지 키, Markdown 렌더링 구현

- [x] 완료

### 목표

Outlook 의존 없이 테스트 가능한 순수 로직으로 이메일을 Obsidian에서 읽기 좋은 Markdown 파일로 변환한다.

### 작업

- 파일명 sanitization과 긴 제목 truncation을 구현한다.
- stable message key 생성 로직을 구현한다.
- YAML frontmatter 생성기를 구현한다.
- 이메일 본문 Markdown 렌더러를 구현한다.
- 첨부파일과 original `.msg` 경로를 vault-relative path로 기록한다.
- 중복 파일명을 message key 또는 hash로 회피한다.

### 검증 조건

- unsafe filename 문자가 제거 또는 대체된다.
- 긴 subject가 안전하게 잘리고 확장자와 message key가 보존된다.
- 같은 이메일 입력은 같은 message key와 같은 대상 경로를 만든다.
- message id가 없을 때 conversation id, received time, sender, subject 기반 fallback key가 생성된다.
- 생성된 frontmatter가 유효한 YAML로 파싱된다.
- 생성된 Markdown에 제목, Metadata, Body, Attachments 섹션이 포함된다.
- 단위 테스트가 filename sanitize, message key, frontmatter, Markdown 렌더링을 검증한다.

## Story 4: Outlook 폴더 whitelist 가져오기 MVP

- [x] 완료

### 목표

Windows Outlook LTSC 2021 데스크톱 클라이언트에서 명시적으로 설정된 폴더만 읽어 이메일을 Markdown으로 가져온다.

### 작업

- Outlook COM 자동화 어댑터를 구현한다.
- 설정된 Outlook folder path를 탐색하고 MailItem을 열거한다.
- subject, sender, recipients, received time, body, attachments, conversation metadata를 추출한다.
- 설정되지 않은 폴더는 가져오지 않는다.
- 중복 메시지는 state 기준으로 skip한다.
- `--dry-run`, `--folder`, `--force`, `--verbose` 옵션을 제공한다.

### 검증 조건

- 설정 파일에 있는 Outlook 폴더만 스캔된다.
- 설정되지 않은 폴더의 메일은 가져오지 않는다.
- 한 메일이 하나의 Markdown 파일로 저장된다.
- 재실행 시 중복 Markdown 파일이 생성되지 않는다.
- `--dry-run`은 파일을 쓰지 않고 가져올 대상만 보고한다.
- Outlook 연결 실패, 폴더 누락, 메일 읽기 실패는 로그에 남고 안전하게 처리된다.
- Windows 수동 테스트에서 테스트 메일 1개가 vault에 Markdown으로 생성된다.

## Story 5: `.msg` 원본과 첨부파일 저장

- [x] 완료

### 목표

설정에 따라 Outlook 원본 `.msg`와 일반 첨부파일을 deterministic한 vault 경로에 저장하고 Markdown에서 참조한다.

### 작업

- `.msg` 저장 기능을 구현한다.
- 첨부파일 저장 기능을 구현한다.
- 첨부파일 파일명 sanitize와 중복명 disambiguation을 구현한다.
- 저장 실패가 전체 import를 중단하지 않도록 오류 처리한다.
- frontmatter와 Markdown body에 저장된 relative path를 기록한다.

### 검증 조건

- `save_msg: true`이면 `90_Attachments/email/<message-key>/original.msg`가 생성된다.
- `save_attachments: true`이면 첨부파일이 `90_Attachments/email/<message-key>/` 아래 저장된다.
- 첨부파일명이 충돌해도 파일이 덮어써지지 않는다.
- `.msg` 또는 개별 첨부 저장 실패는 로그에 남고 다른 메일 처리는 계속된다.
- Markdown frontmatter의 `attachments`와 `original_msg` 값은 vault root 기준 상대 경로다.
- Markdown body의 Attachments 섹션에 Obsidian 링크가 포함된다.

## Story 6: Windows-to-Linux SFTP 동기화

- [x] 완료

### 목표

GitHub나 외부 SaaS 없이 Windows Obsidian vault 변경분을 Linux vault copy로 전송한다.

### 작업

- SFTP sync 설정을 구현한다.
- Windows vault 파일을 Linux remote path로 업로드한다.
- `.kb-sync-manifest.json` 기반 변경 감지를 구현하거나 MVP에서 명시적으로 full sync로 제한한다.
- `--import-only`, `--sync-only` 옵션을 구현한다.
- sync 비활성화 옵션을 지원한다.
- 삭제 전파는 MVP에서 하지 않는다.

### 검증 조건

- 새 Markdown 파일이 Linux vault 경로에 업로드된다.
- 변경된 파일이 다시 업로드된다.
- sync disabled 설정에서는 원격 연결을 시도하지 않는다.
- SFTP 연결 실패나 remote path 오류는 로그에 남고 vault/state를 손상시키지 않는다.
- GitHub/GitHub Enterprise를 sync 백엔드로 사용하지 않는다.
- manifest를 구현한 경우 변경 없는 파일은 반복 업로드되지 않는다.

## Story 7: Linux API 설정, vault scanner, frontmatter parser

- [x] 완료

### 목표

Linux의 synced vault를 읽어 Markdown 파일과 YAML frontmatter를 안전하게 파싱하는 기반을 만든다.

### 작업

- `kb_api` Python 패키지와 CLI 진입점을 만든다.
- Linux YAML config를 파싱한다.
- vault path, database path, host, port, token env, ignore dirs를 모델링한다.
- Markdown scanner를 구현한다.
- YAML frontmatter parser를 구현한다.
- hidden/system folder ignore 정책을 적용한다.

### 검증 조건

- 예제 Linux config를 파싱할 수 있다.
- scanner가 vault 아래 `.md` 파일을 재귀적으로 찾는다.
- `.obsidian`, `.trash` 같은 ignore dir는 제외된다.
- frontmatter가 있는 파일과 없는 파일을 모두 처리한다.
- invalid YAML은 로그에 남고 indexer 전체를 중단시키지 않는다.
- 단위 테스트가 scanner와 frontmatter parser를 검증한다.

## Story 8: SQLite FTS 인덱스와 reindex CLI

- [x] 완료

### 목표

Markdown 노트와 이메일을 SQLite에 저장하고 FTS5로 검색 가능한 인덱스를 구축한다.

### 작업

- `notes`, `chunks`, `chunks_fts` 스키마를 구현한다.
- stable note id와 unique path 정책을 구현한다.
- Markdown body를 검색 가능한 chunk로 분리한다.
- `python -m kb_api reindex --config <path>` 명령을 구현한다.
- reindex가 DB를 rebuild 또는 update하도록 구현한다.
- fixture vault를 이용한 통합 테스트를 추가한다.

### 검증 조건

- reindex 명령 실행 후 SQLite DB가 생성된다.
- fixture vault의 이메일과 노트가 `notes` 테이블에 들어간다.
- chunk와 FTS row가 생성된다.
- email metadata인 type, title/subject, sender, received, folder, tags가 query 가능하다.
- reindex는 vault 파일을 수정하지 않는다.
- 통합 테스트가 fixture vault indexing을 검증한다.

## Story 9: 읽기 전용 FastAPI 검색/노트 API

- [x] 완료

### 목표

Cline/Codex가 Linux vault copy를 검색하고 특정 노트를 읽을 수 있는 read-only HTTP API를 제공한다.

### 작업

- `python -m kb_api serve --config <path>` 명령을 구현한다.
- `/health` endpoint를 구현한다.
- bearer token 인증을 구현한다.
- `GET /search` endpoint를 구현한다.
- `GET /notes/by-path` endpoint를 구현한다.
- path traversal 방어를 구현한다.
- 응답에서 source path, metadata, score, excerpt를 제공한다.

### 검증 조건

- `/health`는 인증 없이 `{"status":"ok"}`를 반환한다.
- `/search`, `/notes/by-path`는 `Authorization: Bearer <token>` 없이는 401 또는 403을 반환한다.
- 올바른 token으로 검색하면 관련 fixture 결과가 반환된다.
- 검색 결과에는 path, title, type, metadata, score, excerpt가 포함된다.
- `/notes/by-path`는 vault-relative path만 허용한다.
- `../`, absolute path, vault 밖 파일 접근은 거부된다.
- API는 노트 생성, 수정, 삭제 endpoint를 제공하지 않는다.

## Story 10: AI context API와 admin reindex endpoint

- [x] 완료

### 목표

AI 도구가 질문에 필요한 compact evidence bundle을 받을 수 있게 하고, 인증된 관리자가 API를 통해 reindex를 실행할 수 있게 한다.

### 작업

- `POST /context` endpoint를 구현한다.
- context request의 query, filters, limit 처리를 구현한다.
- evidence item에 path, title, type, received, sender, excerpt, why_relevant를 포함한다.
- `POST /admin/reindex` endpoint를 구현한다.
- admin endpoint 인증과 로깅을 구현한다.

### 검증 조건

- `/context`는 인증 없이는 실패한다.
- `/context`는 기본적으로 과도한 본문을 반환하지 않는다.
- evidence item마다 source path와 metadata가 포함된다.
- 같은 fixture와 같은 query에 대해 결과가 반복 가능하다.
- `/admin/reindex`는 인증 없이는 실패하고, 인증 시 인덱스 통계와 함께 성공 응답을 반환한다.
- admin reindex는 vault 파일을 수정하지 않는다.

## Story 11: Cline/Codex skill 패키지

- [x] 완료

### 목표

Cline/Codex가 KB API를 올바르게 사용할 수 있도록 skill 지침과 검색/읽기 스크립트를 제공한다.

### 작업

- `cline_skill_obsidian_kb/SKILL.md`를 작성한다.
- `scripts/kb_search.py`를 구현한다.
- `scripts/kb_read.py`를 구현한다.
- 가능하면 `scripts/kb_context.py`를 구현한다.
- API base URL과 token은 환경 변수에서 읽는다.
- unsupported write API 호출 금지와 source citation 규칙을 skill에 명시한다.

### 검증 조건

- `SKILL.md`가 과거 메일, 이전 결정, 프로젝트 히스토리, 장애, 회의 노트, 개인 노트 질문에서 KB API를 먼저 사용하라고 지시한다.
- skill이 근거가 약하면 약하다고 말하도록 지시한다.
- scripts가 token을 hardcode하지 않는다.
- `kb_search.py`가 `/search`를 호출하고 결과 path와 metadata를 출력한다.
- `kb_read.py`가 `/notes/by-path`를 호출하고 빈 path를 거부한다.
- `kb_context.py`를 구현한 경우 `/context` evidence를 AI가 읽기 쉬운 형태로 출력한다.

## Story 12: 자동 실행, 서비스, 운영 가이드

- [x] 완료

### 목표

수동 실행뿐 아니라 daily import와 Linux service 실행이 가능한 운영 형태를 갖춘다.

### 작업

- Windows `.bat` 실행 예제를 추가한다.
- Windows Task Scheduler 설정 가이드를 작성한다.
- Linux systemd service 파일 예제를 추가한다.
- Linux API 재시작, 로그 확인, reindex 절차를 문서화한다.
- 일반 오류별 troubleshooting을 작성한다.

### 검증 조건

- Windows 사용자가 PowerShell 또는 `.bat`로 `kb-win-sync`를 실행할 수 있는 명령이 문서화되어 있다.
- Task Scheduler에서 interactive input 없이 daily run이 가능하도록 필요한 조건이 문서화되어 있다.
- systemd service 예제가 `127.0.0.1` 기본 bind와 환경 변수 token 사용을 반영한다.
- Outlook 접근 실패, SFTP 실패, vault path 누락, token 오류, path traversal 오류의 진단 방법이 문서화되어 있다.
- 운영 문서가 실제 명령과 config path 예시를 포함한다.

## Story 13: 보안, 프라이버시, 회귀 테스트 강화

- [x] 완료

### 목표

엔터프라이즈 환경에서 안전하게 사용할 수 있도록 보안 요구사항과 핵심 회귀 테스트를 강화한다.

### 작업

- Git에 들어가면 안 되는 파일 유형을 다시 점검한다.
- API token, SSH key, 이메일 본문 로깅 금지를 테스트 또는 코드 리뷰 체크로 확인한다.
- path traversal 테스트를 보강한다.
- unauthorized API request 테스트를 보강한다.
- 실제 이메일이 아닌 synthetic fixture만 사용한다.
- README 또는 security notes에 로컬 우선 원칙과 외부 SaaS 금지를 명시한다.

### 검증 조건

- 테스트 fixture에 실제 개인 이메일, 실제 첨부파일, 실제 노트가 없다.
- unauthorized request가 모든 non-health endpoint에서 실패한다.
- token 값이 로그에 출력되지 않는다.
- vault 밖 파일 읽기 시도가 거부된다.
- 저장소에 `.msg`, vault, SQLite DB, 로그, private key, `.env`가 tracked file로 포함되어 있지 않다.
- 보안 문서가 GitHub/GitHub Enterprise에 vault 데이터를 저장하지 말라고 명시한다.

## Story 14: MVP end-to-end 검증

- [x] 완료

### 목표

PRD의 Definition of Done을 기준으로 Windows import부터 Linux API, skill script 사용까지 MVP 흐름을 통합 검증한다.

### 작업

- Windows에서 테스트 Outlook 폴더와 테스트 메일로 수동 import를 수행한다.
- 동일 import를 재실행해 중복 방지를 확인한다.
- SFTP sync로 Linux vault copy에 파일이 도착하는지 확인한다.
- Linux에서 reindex를 실행한다.
- API server를 시작하고 `/health`, `/search`, `/notes/by-path`, 가능하면 `/context`를 호출한다.
- Cline/Codex skill script로 검색과 읽기를 수행한다.

### 검증 조건

- 설정된 Outlook 폴더의 테스트 메일이 Markdown으로 생성된다.
- `.msg`와 첨부파일이 설정대로 저장된다.
- 재실행해도 같은 메일의 Markdown이 중복 생성되지 않는다.
- Linux vault copy에 Markdown과 필요한 첨부파일이 도착한다.
- 검색 API가 가져온 이메일을 찾는다.
- read API가 relative path로 노트 본문과 frontmatter를 반환한다.
- skill script가 API를 호출하고 source path, sender, received date를 포함한 결과를 출력한다.
- 저장소에는 실제 vault 데이터나 민감 데이터가 포함되지 않는다.

## Story 15: 모든 문서 최신 상태 업데이트

- [x] 완료

### 목표

구현된 실제 동작, 명령, 설정, 제한사항이 모든 문서에 반영되도록 문서를 최신 상태로 맞춘다.

### 작업

- `README.md`를 실제 설치/설정/실행 흐름에 맞게 업데이트한다.
- `DESIGN.md`를 실제 아키텍처, 데이터 흐름, 스키마, 보안 결정에 맞게 업데이트한다.
- `PLAN.md`의 완료 체크박스와 검증 결과를 최신 상태로 업데이트한다.
- Windows setup guide, Linux setup guide, Cline skill setup guide, security notes, troubleshooting guide를 실제 구현 기준으로 업데이트한다.
- 예제 config와 문서의 명령어가 코드와 일치하는지 확인한다.

### 검증 조건

- 문서에 존재하지 않는 명령, endpoint, config key가 남아 있지 않다.
- README만 보고도 신규 사용자가 MVP를 설치, 설정, 실행할 수 있다.
- DESIGN.md가 구현된 패키지 구조와 API/DB 스키마를 정확히 설명한다.
- security notes가 vault 데이터 Git 저장 금지, read-only API, token 사용, path traversal 방어를 설명한다.
- troubleshooting guide가 PRD의 주요 오류 상황을 다룬다.
- `PLAN.md`의 각 스토리 완료 상태가 실제 구현 상태와 일치한다.
