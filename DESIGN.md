# 설계

## 아키텍처

시스템은 local-first 성격의 세 부분으로 구성된다.

1. Windows의 `kb_win_sync`는 COM automation으로 명시적으로 설정된 Outlook folder를 읽고 Obsidian vault에 Markdown을 쓴다.
2. 선택 사항인 SFTP sync는 vault file을 Linux vault copy로 복사한다. GitHub는 sync backend로 사용하지 않는다.
3. Linux의 `kb_api`는 Markdown file을 SQLite FTS로 index하고 AI tool을 위한 read-only HTTP API를 노출한다.

## 데이터 흐름

```text
Outlook configured folders
  -> kb_win_sync
  -> Obsidian raw Markdown + attachments/.msg artifacts
  -> manifest-backed SFTP file copy
  -> Linux raw vault copy
  -> Cline CLI metadata enrichment
  -> Linux enriched vault copy
  -> kb_api reindex enriched vault
  -> SQLite notes/chunks/chunks_fts
  -> Cline/Codex skill scripts
```

## Windows 패키지

중요 module:

- `config.py`: local config file에서 사용하는 작은 YAML subset을 parse한다.
- `state.py`: save할 때 atomic replace를 사용하는 JSON import state.
- `render.py`: deterministic message key, filename sanitization, target path 생성, frontmatter, Markdown rendering.
- `outlook.py`: Outlook LTSC desktop용 선택적 `pywin32` COM adapter.
- `sync.py`: 선택적 `paramiko` SFTP sync. quality target은 첫 실행 이후 manifest 기반 incremental upload다.

MVP duplicate key는 Internet Message-ID가 있으면 그것을 사용하고, 없으면 conversation id, received time, sender, subject에 대한 SHA-256 hash를 사용한다.

Outlook artifact 처리:

- `.msg` 원본과 일반 첨부파일은 `90_Attachments/email/<message-key>/` 아래에 저장한다.
- Artifact path는 vault-relative이며 Markdown rendering 전에 frontmatter에 쓴다.
- Artifact save failure는 item별로 log에 남기며, vault 자체를 사용할 수 없는 경우가 아니면 전체 run을 중단하지 않는다.

## Linux 패키지

중요 module:

- `scanner.py`: vault 아래 Markdown을 재귀적으로 찾고 `.obsidian`, `.trash`, `.git`을 무시한다.
- `frontmatter.py`: 외부 dependency 없이 frontmatter를 parse한다.
- `enrichment.py`: raw file을 수정하지 않고 raw Markdown과 검증된 Cline JSON metadata를 별도의 enriched Markdown으로 변환한다.
- `indexer.py`: enriched vault에서 SQLite table과 FTS row를 rebuild한다.
- `server.py`: bearer-token auth와 path traversal 방어를 갖춘 standard-library HTTP API.
- `fastapi_app.py`: `.[api]`를 설치한 environment용 선택적 FastAPI app factory. `server.py`와 같은 API contract 및 error shape을 유지해야 한다.

SQLite schema:

- `notes(id, path, title, type, sender, received, folder, tags_json, metadata_json, body)`
- `chunks(id, note_id, chunk_index, text)`
- `chunks_fts(text, note_id, chunk_id)`

검색 품질 목표:

- local SQLite build가 지원하면 FTS5 trigram tokenizer를 우선 사용한다.
- trigram을 사용할 수 없으면 default FTS5 tokenizer로 fallback하고 diagnostic output에 명시한다.
- type, tag, sender, folder, date filter는 `/search`, `/context`, 관련 skill script 전반에서 일관되게 지원한다.

## API 계약

`/health`는 public이며 `{"status":"ok"}`를 반환한다.

그 외 모든 non-admin endpoint는 `Authorization: Bearer $KB_API_TOKEN`이 필요하다.

`/admin/reindex`는 `Authorization: Bearer $KB_API_ADMIN_TOKEN`이 필요하다.

Read endpoint는 indexed vault content만 반환한다. vault에 쓰지 않는다.

## 보안 결정

- 개인 knowledge data는 `.gitignore`로 제외한다.
- 기본 bind address는 `127.0.0.1`이다.
- Token은 environment variable에서 읽고 log에 남기지 않는다.
- Skill script는 빈 read path를 거부하고 token을 hardcode하지 않는다.
- DB lookup 전에 path traversal을 거부한다.
- Test는 synthetic fixture data만 사용한다.
