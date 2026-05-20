# Obsidian KB Skill 사용법

과거 이메일, 이전 결정, 프로젝트 이력, incident, 회의 노트, 개인 노트에 관한 질문에 답하기 전에 이 skill을 사용한다.

규칙:

- API base URL은 `KB_API_BASE_URL`에서 읽고, 기본값은 `http://127.0.0.1:8765`로 둔다.
- bearer token은 `KB_API_TOKEN`에서 읽고, 절대 hardcode하거나 출력하지 않는다.
- 읽기 전용 endpoint인 `/search`, `/notes/by-path`, `/context`만 사용한다.
- write, update, delete endpoint를 호출하거나 만들어내지 않는다.
- source path와 sender, received date 같은 유용한 email metadata를 인용한다.
- evidence가 약하거나 없으면 확신을 과장하지 말고 그 사실을 명확히 말한다.
- 검색된 내용을 외부 SaaS 서비스에 업로드하지 않는다.

스크립트:

- `scripts/kb_search.py "query"`는 KB를 검색한다.
- `scripts/kb_search.py "query" --limit 5 --json`은 raw contract response를 출력한다.
- `scripts/kb_search.py "query" --type email --tag project/project-a --sender "Kim <kim@example.test>" --folder "ProjectA" --after 2026-01-01 --before 2026-12-31`은 지원되는 filter를 적용한다.
- `scripts/kb_read.py "relative/path.md"`는 특정 note를 읽는다.
- `scripts/kb_context.py "question" --type email --tag project/project-a`는 AI 사용을 위한 compact evidence를 반환한다.

계약:

- API/skill contract는 `docs/API_CONTRACT.md`에 문서화되어 있다.
- `/search`는 top-level `results` 배열을 반환한다. 각 item에는 `path`, `title`, `type`, `sender`, `received`, `folder`, `tags`, `chunk_index`, `matched_fields`, `metadata`, `score`, `excerpt`가 포함되어야 한다.
- `/notes/by-path`는 `path`, `title`, `type`, `metadata`, `body`를 반환한다.
- `/context`는 top-level `evidence` 배열을 반환한다. 각 evidence item에는 `path`, `title`, `type`, `sender`, `received`, `excerpt`, `why_relevant`가 포함되어야 한다.
- Error response는 `{"error": {"code": "...", "message": "...", "hint": "..."}}` 형식을 사용하며, `hint`는 생략될 수 있다.
