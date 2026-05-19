# Obsidian KB Skill

Use this skill before answering questions about past emails, prior decisions, project history, incidents, meeting notes, or personal notes.

Rules:

- Read API base URL from `KB_API_BASE_URL`; default to `http://127.0.0.1:8765`.
- Read bearer token from `KB_API_TOKEN`; never hardcode or print it.
- Use only read-only endpoints: `/search`, `/notes/by-path`, and `/context`.
- Do not call or invent write, update, or delete endpoints.
- Cite source paths and useful email metadata such as sender and received date.
- If evidence is weak or missing, say that clearly instead of overstating confidence.
- Do not upload retrieved content to external SaaS services.

Scripts:

- `scripts/kb_search.py "query"` searches the KB.
- `scripts/kb_search.py "query" --limit 5 --json` prints the raw contract response.
- `scripts/kb_search.py "query" --type email --sender "Kim <kim@example.test>" --folder "ProjectA"` applies supported filters.
- `scripts/kb_read.py "relative/path.md"` reads a specific note.
- `scripts/kb_context.py "question"` returns compact evidence for AI use.

Contract:

- The API/skill contract is documented in `docs/API_CONTRACT.md`.
- `/search` returns a top-level `results` array. Each item must include `path`, `title`, `type`, `sender`, `received`, `folder`, `tags`, `chunk_index`, `matched_fields`, `metadata`, `score`, and `excerpt`.
- `/notes/by-path` returns `path`, `title`, `type`, `metadata`, and `body`.
- `/context` returns a top-level `evidence` array. Each evidence item must include `path`, `title`, `type`, `sender`, `received`, `excerpt`, and `why_relevant`.
- Error responses use `{"error": {"code": "...", "message": "...", "hint": "..."}}`; `hint` may be omitted.
