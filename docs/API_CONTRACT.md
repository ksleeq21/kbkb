# KB API and Skill Contract

This document fixes the contract between `cline_skill_obsidian_kb` and `kb_api`.

Contract version: `v1`

Compatibility rule:

- Additive response fields are allowed.
- Existing required fields must not be removed or renamed within `v1`.
- Endpoint paths, methods, auth header format, and top-level response containers are stable for `v1`.
- Breaking changes require a new contract version and coordinated skill script updates.

## Environment

Skill scripts read:

- `KB_API_BASE_URL`: API base URL. Default: `http://127.0.0.1:8765`.
- `KB_API_TOKEN`: bearer token for read-only endpoints.
- `KB_API_LIMIT`: optional default limit for search/context scripts.

Skill scripts do not read `KB_API_ADMIN_TOKEN` and must not call admin endpoints.

## Authentication

All skill endpoints require:

```http
Authorization: Bearer <KB_API_TOKEN>
```

Unauthorized response:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Missing or invalid bearer token"
  }
}
```

## Health

Skill scripts do not need health checks, but setup and diagnostics use them.

Request:

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "contract_version": "v1"
}
```

Deep request:

```http
GET /health?deep=true
```

Response:

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

## Search

Used by:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_search.py "query"
```

Request:

```http
GET /search?q=<query>&limit=10&type=email&tag=project/project-a&sender=Kim&folder=ProjectA&after=2026-01-01&before=2026-12-31
```

Required query parameters:

- `q`: non-empty FTS query.

Optional query parameters:

- `limit`: integer, clamped by the server.
- `type`: exact note type filter.
- `tag`: exact tag filter; a note matches when its `tags` array contains the value.
- `sender`: exact sender filter.
- `folder`: exact folder filter.
- `after`: inclusive ISO date or datetime lower bound for `received`.
- `before`: inclusive ISO date or datetime upper bound for `received`.

Response:

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

Required fields per result:

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

## Read By Path

Used by:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_read.py "20_Emails/ProjectA/example.md"
```

Request:

```http
GET /notes/by-path?path=<vault-relative-path>
```

Path rules:

- Must be vault-relative.
- Must not be absolute.
- Must not contain `..`.

Response:

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

Required fields:

- `path`
- `title`
- `type`
- `metadata`
- `body`

## Context

Used by:

```bash
python3 cline_skill_obsidian_kb/scripts/kb_context.py "question"
```

Request:

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

Response:

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

Required fields per evidence item:

- `path`
- `title`
- `type`
- `received`
- `sender`
- `excerpt`
- `why_relevant`

## Error Shape

Error responses use:

```json
{
  "error": {
    "code": "invalid_query",
    "message": "Search query must not be empty",
    "hint": "Pass a non-empty q parameter or query field."
  }
}
```

Required error fields:

- `error.code`
- `error.message`

Optional error fields:

- `error.hint`

Known codes:

- `unauthorized`
- `bad_request`
- `not_found`
- `database_not_indexed`
- `invalid_query`

Implementation requirement:

Both the standard-library server and the optional FastAPI deployment must return this same top-level `error` object. Framework-native shapes such as FastAPI's default `{"detail": ...}` are not contract-compatible for v1 endpoints.
