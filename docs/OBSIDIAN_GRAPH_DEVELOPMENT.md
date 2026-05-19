# Obsidian Email Knowledge Graph Development Plan

이 문서는 Outlook 이메일을 Obsidian Markdown vault로 변환하고, 그 Markdown을 SQLite FTS와 graph index로 옮겨 지식 검색을 만드는 개발 계획이다.

핵심 방향은 단순하다.

1. Windows에서 이메일을 먼저 안정적인 raw Markdown 파일로 만든다.
2. Linux에서 raw Markdown을 입력으로 Cline CLI를 실행해 LLM 보강 metadata를 만든다.
3. Cline CLI 결과를 검증한 뒤 raw Markdown을 덮어쓰지 않고 enriched Markdown 파일을 새로 만든다.
4. enriched Markdown 파일을 검색과 graph index의 source of truth로 둔다.
5. SQLite는 검색과 graph traversal을 위한 index/cache로 사용한다.
6. 처음부터 GraphRAG, Neo4j, embeddings에 의존하지 않는다.

## 목표

사용자는 다음과 같은 질문으로 이메일과 관련 문서를 찾을 수 있어야 한다.

```text
개발망 회의록
개발망 미팅
Kim이 보낸 개발망 관련 메일
이 회의록과 같은 conversation의 다른 메일
이 이메일에 연결된 첨부파일
```

MVP의 검색 품질은 LLM reasoning보다 명시적인 구조와 본문 검색에 기대어 만든다.

- 이메일 subject/body에 있는 단어를 찾는다.
- YAML frontmatter의 tag, sender, recipient, conversation을 찾는다.
- 첨부파일 filename/path를 찾는다.
- `[[wiki links]]`와 backlinks로 연결된 note를 찾는다.
- 같은 tag/folder/conversation/person 관계를 boost한다.

## 전체 파이프라인

```text
Outlook email / .msg / export source
  -> 원본 metadata와 body 추출
  -> 첨부파일 저장
  -> Windows raw Obsidian Markdown 생성
  -> Linux로 raw Markdown 동기화
  -> Cline CLI로 raw Markdown을 입력받아 LLM metadata 생성
  -> metadata 검증 및 정규화
  -> raw Markdown은 보존하고 enriched Markdown 새로 생성
  -> enriched Markdown vault를 SQLite reindex
  -> FTS5/trigram 검색 index 생성
  -> graph/search API 제공
```

## Raw/Enriched Markdown 원칙

이 시스템에는 두 종류의 Markdown이 있다.

- Raw Markdown: Windows `kb_win_sync`가 Outlook 원본에서 deterministic하게 만든 파일
- Enriched Markdown: Linux에서 Cline CLI 결과를 검증한 뒤 raw Markdown에 metadata를 적용해 새로 만든 파일

Raw Markdown은 원본 변환 결과이므로 Linux enrichment 단계에서 덮어쓰지 않는다. Enriched Markdown은 검색과 graph index의 source of truth다.

DB는 source of truth가 아니라 조회 성능을 위한 재생성 가능한 index다. DB가 깨지거나 삭제되어도 enriched vault의 Markdown을 다시 읽어 같은 DB를 만들 수 있어야 한다.

개발 원칙:

1. Windows는 raw Markdown만 생성한다.
2. Linux Cline CLI enrichment는 raw Markdown을 입력으로 사용한다.
3. Linux enrichment는 raw Markdown을 수정하지 않고 enriched Markdown을 새로 생성한다.
4. `kb_api`는 enriched Markdown vault만 reindex한다.
5. DB에서 vault 파일을 직접 수정하지 않는다.
6. GitHub에는 실제 vault 데이터, `.msg` 원본, 첨부파일, SQLite DB를 저장하지 않는다.
7. reindex는 idempotent해야 한다.
8. LLM이 만든 metadata는 검증 후 저장한다.
9. 원본에서 확정 가능한 metadata와 LLM 추론 metadata를 분리한다.
10. embeddings, entity extraction, GraphRAG는 MVP 이후 단계로 미룬다.

## Obsidian 구조를 Graph로 보는 법

Obsidian의 기본 기능은 이미 graph의 재료다.

- Markdown file: note node
- Folder path: note의 위치와 분류
- YAML frontmatter: note metadata
- Tags: topic/project/category node
- `[[wiki links]]`: note-to-note edge
- Backlinks: wiki link의 역방향 edge
- Attachments: file node
- Outlook email metadata: person, conversation, folder, attachment 관계

예를 들어 어떤 이메일 Markdown 본문에 다음 문장이 있으면:

```markdown
개발망 작업 절차는 [[개발망 운영 가이드]]를 참고하세요.
```

이 문서는 `개발망 운영 가이드` note를 향하는 edge를 가진다. 반대로 `개발망 운영 가이드` 입장에서는 이 이메일이 backlink다.

## Email Markdown 형식

Windows importer가 만드는 raw Markdown은 Obsidian에서 읽기 좋고, 원본 Outlook metadata만 담는다. Linux enrichment가 만드는 enriched Markdown은 raw Markdown의 본문과 원본 metadata를 유지하면서 LLM 보강 metadata를 추가한다.

Raw Markdown 예:

```markdown
---
type: email
source: outlook
source_id: "AAMkAG..."
source_checksum: "sha256:..."
subject: "개발망 미팅 회의록 공유"
from: "Kim <kim@example.com>"
to:
  - "Lee <lee@example.com>"
cc: []
sent_at: "2026-05-19T09:30:00+09:00"
received_at: "2026-05-19T09:31:12+09:00"
conversation_id: "abc-123"
outlook_folder: "Inbox/Project/DevNet"
original_msg_path: "90_Attachments/email/abc/original.msg"
attachments:
  - path: "90_Attachments/email/abc/개발망_회의록.docx"
    filename: "개발망_회의록.docx"
    content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
tags:
  - email
  - mailbox/devnet
---

# 개발망 미팅 회의록 공유

개발망 미팅 회의록 전달드립니다.

첨부파일 확인 부탁드립니다.
```

Enriched Markdown 예:

```markdown
---
type: email
source: outlook
source_id: "AAMkAG..."
source_checksum: "sha256:..."
subject: "개발망 미팅 회의록 공유"
from: "Kim <kim@example.com>"
to:
  - "Lee <lee@example.com>"
cc: []
sent_at: "2026-05-19T09:30:00+09:00"
received_at: "2026-05-19T09:31:12+09:00"
conversation_id: "abc-123"
outlook_folder: "Inbox/Project/DevNet"
original_msg_path: "90_Attachments/email/abc/original.msg"
attachments:
  - path: "90_Attachments/email/abc/개발망_회의록.docx"
    filename: "개발망_회의록.docx"
    content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
tags:
  - email
  - mailbox/devnet
  - 개발망
  - 회의록
llm_tags:
  - 인프라
  - 개발환경
llm_summary: "개발망 미팅 회의록을 공유한 이메일."
llm_model: "..."
llm_indexed_at: "2026-05-19T10:00:00+09:00"
---

# 개발망 미팅 회의록 공유

개발망 미팅 회의록 전달드립니다.

첨부파일 확인 부탁드립니다.
```

## Metadata 생성 책임

YAML frontmatter는 자동으로 생기는 것이 아니다. 다음 세 단계가 역할을 나눠 만든다.

### 1. Importer가 만드는 원본 metadata

원본 이메일에서 확정적으로 얻을 수 있는 값은 importer가 만든다.

- `type`
- `source`
- `source_id`
- `source_checksum`
- `subject`
- `from`
- `to`
- `cc`
- `sent_at`
- `received_at`
- `conversation_id`
- `outlook_folder`
- `original_msg_path`
- `attachments`

특히 `conversation_id`, `source_id`, 날짜, 발신자, 수신자는 LLM이 만들면 안 된다. 원본에서 가져오거나 deterministic hash로 계산해야 한다.

### 2. Linux Cline CLI가 보강하는 metadata

Cline CLI는 raw Markdown을 입력으로 받아 사람이 검색할 때 도움이 되는 보강 metadata를 만든다.

- `tags`
- `llm_tags`
- `llm_summary`
- 관련 note 후보
- 제목 정규화 후보
- 첨부파일 설명 후보

LLM metadata는 추론값이므로 원본 metadata와 분리한다.

Cline CLI 단계의 입출력은 테스트 가능해야 한다.

```text
input: raw Markdown
cline output: JSON object only
validator output: accepted/rejected metadata
output: enriched Markdown
```

Raw Markdown을 직접 수정하지 않기 때문에 같은 raw fixture와 같은 Cline output fixture로 enriched Markdown 생성 테스트를 반복할 수 있다.

### 3. Validator가 검증하고 정규화하는 metadata

LLM 출력은 그대로 저장하지 않는다. enriched Markdown 생성 전 validator가 다음을 확인한다.

- YAML 또는 JSON 문법이 valid한가
- 필수 필드가 있는가
- 이메일 주소가 원문 metadata와 충돌하지 않는가
- LLM이 `conversation_id`, `source_id`, `sent_at` 같은 원본 필드를 지어내지 않았는가
- tag 수가 과도하지 않은가
- 허용되지 않은 tag 또는 중복 tag가 있는가
- 파일 경로가 vault 내부 상대 경로인가

## Cline CLI를 이용한 Enrichment

Linux enrichment 단계는 Cline CLI로 처리한다.

Cline CLI 문서: <https://docs.cline.bot/cli/cli-reference>

문서 기준으로 Cline CLI는 다음 형태를 지원한다.

```bash
cline "your prompt here"
echo "prompt" | cline
cline --json --cwd <workspace> --timeout <seconds> "your prompt here"
```

자동화에서는 `--json`, `--cwd`, `--timeout`, `--model`, `--provider`, `--system` 옵션을 우선 고려한다.

권장 방식은 Cline에게 Markdown 파일 전체나 YAML frontmatter 전체를 직접 쓰게 하는 것이 아니라, 정해진 JSON schema만 출력하게 한 뒤 enrichment script가 enriched Markdown을 생성하는 것이다.

예:

```json
{
  "tags": ["개발망", "회의록"],
  "llm_tags": ["인프라", "개발환경"],
  "llm_summary": "개발망 미팅 회의록을 공유한 이메일."
}
```

그 이유는 JSON schema 검증이 쉽고, LLM이 frontmatter 전체를 망가뜨리거나 raw Markdown을 변경할 위험이 작기 때문이다.

권장 파일 흐름:

```text
KnowledgeVault-Raw/20_Emails/ProjectA/example.md
  -> cline --json
cline-enrichment-cache/20_Emails/ProjectA/example.metadata.json
  -> validator
KnowledgeVault-Enriched/20_Emails/ProjectA/example.md
```

`KnowledgeVault-Raw`는 Windows sync 결과를 보존한다. `KnowledgeVault-Enriched`는 `kb_api`가 reindex하는 대상이다.

실행 계약:

```bash
python3 -m kb_api enrich --config ~/.config/kb-api/config.yaml
```

테스트에서는 실제 Cline CLI 호출 없이 cache JSON을 사용한다.

```bash
python3 -m kb_api enrich --config ~/.config/kb-api/config.yaml --use-cache-only
```

첨부파일 정책은 `copy`로 고정한다. Raw vault의 Markdown이 아닌 파일은 enriched vault에 복사한다. Symlink는 Windows/SFTP/Obsidian 경계에서 깨질 수 있으므로 사용하지 않는다.

### Cline Prompt 원칙

프롬프트에는 다음 제한을 명시한다.

- 원본 metadata를 수정하지 말 것
- `source_id`, `conversation_id`, 날짜, 발신자, 수신자를 생성하지 말 것
- 제공된 본문과 제목에서 근거가 있는 tag만 만들 것
- 출력은 JSON object 하나만 만들 것
- tag는 지정된 taxonomy를 우선 사용할 것
- 민감정보를 요약에 불필요하게 반복하지 말 것

## Tag Taxonomy

LLM이 자유롭게 tag를 만들면 같은 의미의 tag가 여러 이름으로 갈라진다.

예:

```text
개발망
개발 망
개발환경망
Dev Network
회의록
미팅노트
meeting-minutes
```

초기부터 tag taxonomy와 normalization 규칙을 둔다.

예:

```text
개발 망 -> 개발망
개발환경망 -> 개발망
Dev Network -> 개발망
미팅노트 -> 회의록
회의 메모 -> 회의록
meeting-minutes -> 회의록
```

권장 정책:

- `tags`: 검색과 필터에 쓰는 정규화된 핵심 tag
- `llm_tags`: LLM이 제안한 보조 tag
- `raw_tags`: 원문 또는 기존 Obsidian tag를 보존해야 할 때 사용

## SQLite FTS 검색 전략

SQLite FTS는 Full-Text Search용 index다.

일반적인 `LIKE '%개발망%'` 검색은 문서가 많아지면 느리고, 검색 순위 계산도 약하다. FTS는 본문을 미리 token으로 나눠 검색 전용 index를 만든다.

개념적으로는 다음과 같다.

```text
개발망 -> note 12, note 88, note 102
회의록 -> note 12, note 40
미팅 -> note 12, note 77
```

사용자가 `개발망 회의록`을 검색하면 FTS는 두 단어가 등장하는 chunk를 빠르게 찾고, `bm25` 같은 ranking 함수를 통해 점수를 계산한다.

## 한국어 검색 전략

한국어는 띄어쓰기와 복합어 때문에 기본 tokenizer만으로 부족할 수 있다.

예:

```text
개발망 회의록
개발망회의록
개발망관련회의록입니다
```

MVP 권장 전략:

1. FTS5 `trigram` tokenizer를 우선 검토한다.
2. 제목, 본문, tag, 첨부파일명을 별도 필드로 index하고 boost한다.
3. 실제 검색 로그를 보고 부족하면 n-gram index 또는 한국어 형태소 분석기를 추가한다.

권장 FTS table 예:

```sql
CREATE VIRTUAL TABLE chunks_fts
USING fts5(
  title,
  body,
  tags,
  attachment_names,
  note_id UNINDEXED,
  chunk_id UNINDEXED,
  tokenize = 'trigram'
);
```

주의:

- SQLite 빌드에 따라 trigram tokenizer 지원 여부를 확인해야 한다.
- trigram은 부분 문자열 검색에 강하지만 index 크기가 커질 수 있다.
- 형태소 분석기는 품질이 좋을 수 있지만 운영 복잡도가 올라간다.

MVP는 FTS5 trigram과 metadata boost로 시작하고, 검색 품질이 부족할 때 형태소 분석기를 붙인다.

## Graph-Boosted Search

검색 결과는 FTS 점수만으로 정렬하지 않는다. graph와 metadata 신호를 더한다.

예:

```text
final_score = fts_score
            + subject_boost
            + tag_boost
            + attachment_name_boost
            + folder_boost
            + link_boost
            + conversation_boost
            + people_boost
```

검색어 `개발망 회의록`에 대한 ranking 예:

- subject에 `개발망`, `회의록`이 모두 있으면 크게 boost한다.
- body에 두 단어가 모두 있으면 boost한다.
- tag에 `개발망`, `회의록`이 있으면 크게 boost한다.
- 첨부파일명에 `회의록`이 있으면 boost한다.
- 같은 conversation의 다른 이메일은 related result로 boost한다.
- 직접 `[[개발망 운영 가이드]]`를 링크하면 neighbor로 노출한다.

## 첨부파일 검색

회의록은 이메일 본문보다 첨부파일 안에 있을 가능성이 높다. 첨부파일 검색 범위를 명확히 정해야 한다.

MVP 최소 범위:

- 첨부파일 path 저장
- 첨부파일 filename 저장
- filename을 FTS 검색 대상에 포함

다음 단계:

- `.docx` 텍스트 추출
- `.pdf` 텍스트 추출
- `.xlsx` sheet text 추출
- attachment text를 `attachment_chunks`로 저장
- attachment hit를 parent email 검색 점수에 합산

첨부파일 내부 텍스트까지 검색하려면 attachment도 별도 document node로 취급하는 것이 좋다.

## Recommended SQLite Schema

### notes

`notes`는 vault 안의 Markdown 파일 하나를 의미한다.

```sql
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  folder_path TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  body TEXT NOT NULL,
  source_id TEXT,
  source_checksum TEXT,
  indexed_at TEXT NOT NULL
);
```

### chunks

`chunks`는 긴 note 본문을 검색하기 좋은 작은 조각으로 나눈 것이다.

```sql
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  title TEXT NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY(note_id) REFERENCES notes(id)
);
```

### chunks_fts

`chunks_fts`는 SQLite full-text search용 table이다.

```sql
CREATE VIRTUAL TABLE chunks_fts
USING fts5(
  title,
  body,
  tags,
  attachment_names,
  note_id UNINDEXED,
  chunk_id UNINDEXED,
  tokenize = 'trigram'
);
```

### links

`links`는 `[[wiki links]]`를 저장한다.

```sql
CREATE TABLE links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_note_id TEXT NOT NULL,
  target_text TEXT NOT NULL,
  target_note_id TEXT,
  link_text TEXT NOT NULL,
  link_type TEXT NOT NULL DEFAULT 'wiki',
  FOREIGN KEY(source_note_id) REFERENCES notes(id),
  FOREIGN KEY(target_note_id) REFERENCES notes(id)
);
```

처음에는 `target_note_id`가 비어 있어도 된다. reindex 마지막 단계에서 가능한 범위만 resolve한다.

### tags

```sql
CREATE TABLE tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  normalized_name TEXT NOT NULL
);
```

### note_tags

```sql
CREATE TABLE note_tags (
  note_id TEXT NOT NULL,
  tag_id INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'frontmatter',
  PRIMARY KEY(note_id, tag_id, source),
  FOREIGN KEY(note_id) REFERENCES notes(id),
  FOREIGN KEY(tag_id) REFERENCES tags(id)
);
```

`source` 예:

- `frontmatter`
- `llm`
- `inline`
- `importer`

### folders

```sql
CREATE TABLE folders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  parent_path TEXT
);
```

### attachments

```sql
CREATE TABLE attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id TEXT NOT NULL,
  path TEXT NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT,
  attachment_type TEXT NOT NULL,
  text_indexed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(note_id) REFERENCES notes(id)
);
```

### attachment_chunks

첨부파일 내부 텍스트를 검색하려면 사용한다.

```sql
CREATE TABLE attachment_chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attachment_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY(attachment_id) REFERENCES attachments(id)
);
```

### people

```sql
CREATE TABLE people (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  display_name TEXT,
  email TEXT UNIQUE
);
```

### email_people

```sql
CREATE TABLE email_people (
  note_id TEXT NOT NULL,
  person_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  PRIMARY KEY(note_id, person_id, role),
  FOREIGN KEY(note_id) REFERENCES notes(id),
  FOREIGN KEY(person_id) REFERENCES people(id)
);
```

`role` 예:

- `from`
- `to`
- `cc`
- `bcc`

### conversations

```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  subject TEXT,
  first_received TEXT,
  last_received TEXT
);
```

### note_conversations

```sql
CREATE TABLE note_conversations (
  note_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  FOREIGN KEY(note_id) REFERENCES notes(id),
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
```

## Reindex 동작 순서

`reindex`는 다음 순서로 동작한다.

1. vault 아래 `.md` 파일을 찾는다.
2. frontmatter와 body를 파싱한다.
3. metadata schema를 검증한다.
4. `notes`에 note 한 줄을 upsert한다.
5. body를 chunk로 나눠 `chunks`, `chunks_fts`에 저장한다.
6. frontmatter의 `tags`, `llm_tags`를 정규화해 `tags`, `note_tags`에 저장한다.
7. file path에서 folder를 계산해 `folders`에 저장한다.
8. body에서 `[[wiki links]]`를 찾아 `links`에 저장한다.
9. `attachments`, `original_msg_path`를 `attachments`에 저장한다.
10. 첨부파일 내부 텍스트 추출이 켜져 있으면 `attachment_chunks`에 저장한다.
11. `type=email`이면 sender/recipients를 `people`, `email_people`에 저장한다.
12. `conversation_id`가 있으면 `conversations`, `note_conversations`에 저장한다.
13. 모든 note를 읽은 뒤 `links.target_note_id`를 가능한 범위에서 resolve한다.

## Link Resolution

Obsidian `[[wiki links]]`는 반드시 정확한 파일 경로를 담고 있지 않을 수 있다.

예:

```markdown
[[Project A Runbook]]
[[Project A Runbook|runbook]]
[[20_Emails/ProjectA/Incident]]
```

초기 resolver는 단순하게 시작한다.

1. `target_text`가 note path와 정확히 일치하면 연결한다.
2. 아니면 note title과 일치하면 연결한다.
3. 아니면 `.md` 확장자를 붙이거나 제거해 다시 비교한다.
4. 여러 개가 매칭되면 `target_note_id`는 비워두고 `target_text`만 유지한다.

애매한 link를 억지로 연결하지 않는 것이 낫다.

## API

### Search

```http
GET /search?q=개발망%20회의록
```

출력 예:

```json
{
  "query": "개발망 회의록",
  "results": [
    {
      "path": "20_Emails/DevNet/2026-05-19-개발망-미팅-회의록.md",
      "title": "개발망 미팅 회의록 공유",
      "type": "email",
      "score": 18.4,
      "matched_fields": ["subject", "body", "tags", "attachment_names"],
      "excerpt": "개발망 미팅 회의록 전달드립니다."
    }
  ]
}
```

### Backlinks

```http
GET /graph/backlinks?path=10_Notes/개발망-운영-가이드.md
```

### Neighbors

```http
GET /graph/neighbors?path=20_Emails/DevNet/example.md&depth=1
```

### Email Graph

```http
GET /graph/email?path=20_Emails/DevNet/example.md
```

출력 예:

```json
{
  "path": "20_Emails/DevNet/example.md",
  "people": [
    {"role": "from", "email": "kim@example.com", "display_name": "Kim"},
    {"role": "to", "email": "lee@example.com", "display_name": "Lee"}
  ],
  "conversation_id": "abc-123",
  "attachments": [
    "90_Attachments/email/abc/개발망_회의록.docx"
  ]
}
```

### Tags and Folders

```http
GET /tags
GET /folders
```

## Idempotency와 중복 방지

같은 이메일을 여러 번 처리해도 Markdown과 DB가 중복되면 안 된다.

필요한 정책:

- `source_id`가 있으면 primary identity로 사용한다.
- `source_id`가 없으면 subject/from/sent_at/body checksum으로 deterministic id를 만든다.
- Markdown path는 deterministic하게 만든다.
- 같은 `source_checksum`이면 LLM 재처리를 생략한다.
- LLM 결과는 cache한다.
- 실패한 이메일은 재시도 큐에 남긴다.
- reindex는 기존 rows를 삭제 후 재삽입하거나 transaction 안에서 upsert한다.

## 보안과 개인정보

이메일은 민감정보를 포함할 수 있다. LLM과 검색 index 모두 보안 고려가 필요하다.

확인할 것:

- 외부 LLM으로 이메일 본문을 보내도 되는가
- Cline CLI 로그에 이메일 원문이 남는가
- `.msg`, 첨부파일, SQLite DB가 Git에 올라가지 않도록 `.gitignore`가 되어 있는가
- LLM prompt에 필요한 최소 본문만 보내는가
- 민감정보 마스킹이 필요한가
- 사내망/계약/개인정보 키워드를 별도 보호해야 하는가

## 개발 단계

### Phase 0: Email to Markdown

- Outlook email 원본에서 metadata/body/attachments를 추출한다.
- deterministic Markdown path를 만든다.
- 원본 metadata로 기본 frontmatter를 만든다.
- 원본 `.msg`와 첨부파일을 vault 내부 attachment path에 저장한다.
- Windows에서 생성한 raw Markdown을 Linux raw vault로 동기화한다.

### Phase 1: Linux Cline CLI Enrichment

- Raw Markdown을 입력으로 Cline CLI를 실행해 tag, summary, 보조 metadata를 생성한다.
- Cline 출력은 JSON schema로 제한한다.
- validator로 검증한 뒤 raw Markdown을 덮어쓰지 않고 enriched Markdown을 새로 생성한다.
- tag taxonomy와 normalization을 적용한다.
- Cline CLI를 호출하지 않는 테스트에서는 `raw.md + cline-output.json -> enriched.md` fixture로 검증한다.

### Phase 2: SQLite FTS

- `notes`, `chunks`, `chunks_fts`를 만든다.
- `kb_api`는 raw vault가 아니라 enriched vault를 reindex한다.
- FTS5 trigram tokenizer를 적용한다.
- subject/body/tags/attachment filenames를 검색 대상으로 넣는다.
- `/search` API를 만든다.

### Phase 3: Obsidian Graph

- `links`, `tags`, `note_tags`, `folders`, `attachments`를 만든다.
- `[[wiki links]]`를 파싱한다.
- backlinks와 neighbors API를 만든다.

### Phase 4: Email Graph

- `people`, `email_people`, `conversations`, `note_conversations`를 만든다.
- person/conversation/email-neighbors API를 만든다.
- 같은 sender/recipient/conversation 기반 related results를 제공한다.

### Phase 5: Attachment Text Search

- `.docx`, `.pdf`, `.xlsx` 내부 텍스트를 추출한다.
- `attachment_chunks`와 attachment FTS를 만든다.
- attachment hit를 parent email 점수에 합산한다.

### Phase 6: Optional Semantic Layer

필요하면 MVP 이후 추가한다.

- embeddings table
- local embedding model
- entities table
- relations table
- LightRAG/GraphRAG PoC

이 단계는 Obsidian-native graph와 FTS 기반 검색이 안정화된 뒤 진행한다.

## 왜 GraphRAG보다 먼저 이 방식인가

이 접근은 MVP에 더 적합하다.

- cloud service가 필요 없다.
- embedding dependency가 없다.
- entity extraction 품질 리스크가 작다.
- reindex가 deterministic하다.
- raw Markdown과 Cline output fixture로 enrichment를 독립 테스트하기 쉽다.
- synthetic fixture로 테스트하기 쉽다.
- code review에서 설명하기 쉽다.
- Obsidian의 실제 데이터 모델과 직접 맞는다.
- 이메일 검색의 대부분은 subject/body/tag/attachment/person/conversation 같은 명시적 단서로 해결된다.

GraphRAG는 나중에 붙일 수 있다. 다만 그 전에 Markdown, metadata, FTS, graph table이 단단해야 한다.

## MVP 완료 기준

MVP는 다음이 가능하면 완료로 본다.

- 이메일 하나가 Markdown 파일 하나로 안정적으로 생성된다.
- Windows raw Markdown이 Linux raw vault로 동기화된다.
- Linux Cline CLI enrichment가 raw Markdown을 덮어쓰지 않고 enriched Markdown을 생성한다.
- 원본 metadata와 LLM metadata가 enriched Markdown frontmatter에 분리 저장된다.
- `개발망 회의록` 검색으로 subject/body/tag/attachment filename이 맞는 이메일을 찾는다.
- 같은 conversation의 이메일을 related result로 볼 수 있다.
- `[[wiki links]]`와 backlinks를 조회할 수 있다.
- DB를 삭제하고 enriched vault를 reindex해도 같은 결과를 재생성할 수 있다.
