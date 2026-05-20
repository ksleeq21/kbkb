# KB API 및 Skill 계약

이 문서는 `cline_skill_obsidian_kb`와 `kb_api` 사이의 contract를 고정한다.

계약 버전: `v1`

호환성 규칙:

- 응답 field 추가는 허용된다.
- 기존 required field는 `v1` 안에서 제거하거나 이름을 바꾸면 안 된다.
- Endpoint path, method, auth header format, top-level response container는 `v1`에서 stable이다.
- Breaking change에는 새 contract version과 coordinated skill script update가 필요하다.

## 환경

Skill script는 다음 값을 읽는다.

- `KB_API_BASE_URL`: API base URL. 기본값: `http://127.0.0.1:8765`.
- `KB_API_TOKEN`: read-only endpoint용 bearer token.
- `KB_API_LIMIT`: search/context script의 선택적 default limit.

Skill script는 `KB_API_ADMIN_TOKEN`을 읽지 않으며 admin endpoint를 호출하면 안 된다.

## 인증

모든 skill endpoint에는 다음 header가 필요하다.

```http
Authorization: Bearer <KB_API_TOKEN>
```

인증 실패 응답:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Missing or invalid bearer token"
  }
}
```

## 상태 확인

Skill script에는 health check가 필요 없지만 setup과 diagnostic에서 사용한다.

요청:

```http
GET /health
```

응답:

```json
{
  "status": "ok",
  "contract_version": "v1"
}
```

심층 요청:

```http
GET /health?deep=true
```

응답:

```json
{
  "status": "ok",
  "contract_version": "v1",
  "database_exists": true,
  "notes": 2,
  "chunks": 2,
  "newest_received": "2026-05-19T09:15:00+09:00",
  "fts_tokenizer": "trigram"
}
```

## 검색

사용 예:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_search.py "query"
```

요청:

```http
GET /search?q=<query>&limit=10&type=email&tag=project/project-a&sender=Kim&folder=ProjectA&after=2026-01-01&before=2026-12-31
```

필수 query parameter:

- `q`: 비어 있지 않은 FTS query.

선택 query parameter:

- `limit`: integer이며 server가 clamp한다.
- `type`: 정확히 일치하는 note type filter.
- `tag`: 정확히 일치하는 tag filter. note의 `tags` array가 해당 값을 포함하면 match된다.
- `sender`: 정확히 일치하는 sender filter.
- `folder`: 정확히 일치하는 folder filter.
- `after`: `received`에 대한 inclusive ISO date 또는 datetime lower bound.
- `before`: `received`에 대한 inclusive ISO date 또는 datetime upper bound.

응답:

```json
{
  "results": [
    {
      "path": "20_Emails/ProjectA/example.md",
      "title": "Synthetic SSO incident analysis",
      "type": "email",
      "sender": "Kim <kim@example.test>",
      "received": "2026-05-19T09:15:00+09:00",
      "folder": "\\Mailbox - User Name\\Inbox\\_KB\\ProjectA",
      "tags": ["email", "project/project-a"],
      "chunk_index": 0,
      "matched_fields": ["body"],
      "metadata": {
        "type": "email"
      },
      "score": -0.123,
      "excerpt": "Matched text excerpt"
    }
  ]
}
```

Result별 필수 field:

- `path`
- `title`
- `type`
- `sender`
- `received`
- `folder`
- `tags`
- `chunk_index`
- `matched_fields`
- `metadata`
- `score`
- `excerpt`

## 경로로 읽기

사용 예:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_read.py "20_Emails/ProjectA/example.md"
```

요청:

```http
GET /notes/by-path?path=<vault-relative-path>
```

Path rule:

- vault-relative여야 한다.
- absolute이면 안 된다.
- `..`를 포함하면 안 된다.

응답:

```json
{
  "path": "20_Emails/ProjectA/example.md",
  "title": "Synthetic SSO incident analysis",
  "type": "email",
  "metadata": {
    "type": "email"
  },
  "body": "# Synthetic SSO incident analysis\n..."
}
```

Required field:

- `path`
- `title`
- `type`
- `metadata`
- `body`

## Context 응답

사용 예:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_context.py "question"
```

요청:

```http
POST /context
Content-Type: application/json
```

Body:

```json
{
  "query": "SSO incident",
  "limit": 5,
  "filters": {
    "type": "email",
    "tag": "project/project-a",
    "after": "2026-01-01",
    "before": "2026-12-31"
  }
}
```

응답:

```json
{
  "evidence": [
    {
      "path": "20_Emails/ProjectA/example.md",
      "title": "Synthetic SSO incident analysis",
      "type": "email",
      "received": "2026-05-19T09:15:00+09:00",
      "sender": "Kim <kim@example.test>",
      "excerpt": "Matched text excerpt",
      "why_relevant": "Matched the context query through the local SQLite FTS index."
    }
  ]
}
```

Evidence item별 필수 field:

- `path`
- `title`
- `type`
- `received`
- `sender`
- `excerpt`
- `why_relevant`

## 오류 형식

Error response는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "invalid_query",
    "message": "Search query must not be empty",
    "hint": "Pass a non-empty q parameter or query field."
  }
}
```

필수 error field:

- `error.code`
- `error.message`

선택 error field:

- `error.hint`

알려진 code:

- `unauthorized`
- `bad_request`
- `not_found`
- `database_not_indexed`
- `invalid_query`

구현 요구사항:

standard-library server와 optional FastAPI deployment는 같은 top-level `error` object를 반환해야 한다. FastAPI default `{"detail": ...}` 같은 framework-native shape은 v1 endpoint contract와 호환되지 않는다.
