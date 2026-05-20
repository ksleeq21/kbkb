# Cline Enrichment 직접 테스트

이 문서는 `kb-api enrich`가 내부에서 Cline CLI에 요청하는 metadata 생성을 파일 하나로 직접 테스트하는 방법을 설명한다.

목표는 raw Markdown을 Cline에 넣어 JSON metadata만 받고, 그 결과를 cache 파일로 저장한 뒤 `kb-api enrich --use-cache-only`로 검증하는 것이다.

## 전제

- Linux raw vault에 테스트할 Markdown 파일이 있다.
- `cline` CLI가 shell에서 실행 가능하다.
- `kb-api` config의 `raw_vault_path`, `enriched_vault_path`, `enrichment_cache_path`가 설정되어 있다.

현재 기본 metadata provider는 Cline CLI다. `kb_api.enrichment`의 vault/cache/render 흐름은 provider interface만 호출하므로, 이후 REST API 기반 provider를 추가하더라도 raw Markdown 처리와 validation 흐름은 그대로 유지한다.

예시에서는 raw vault 기준 상대 경로를 사용한다.

```bash
REL_PATH="20_Emails/ProjectA/example.md"
RAW_FILE="$HOME/kb/KnowledgeVault-Raw/$REL_PATH"
CACHE_FILE="$HOME/.local/share/kb-api/enrichment-cache/${REL_PATH%.md}.metadata.json"
```

실제 환경의 raw vault 또는 cache path가 다르면 위 값만 바꾼다.

## 직접 Cline 실행

Cline은 정확히 JSON object 하나만 출력해야 한다. 허용되는 key는 `tags`, `llm_tags`, `llm_summary`뿐이다.

```bash
cline --json "$(cat <<EOF
Return exactly one JSON object with only these optional keys: tags, llm_tags, llm_summary.
Do not include source metadata such as type, source, subject, from, to, dates, source_id, message_id, conversation_id, attachments, or folder.
Use evidence from this raw Markdown only.

$(cat "$RAW_FILE")
EOF
)"
```

Cline CLI의 `--json` 출력은 JSON object 하나가 아니라 여러 message JSON으로 나올 수 있다. 이 경우 최종 metadata는 다음 조건을 만족하는 message의 `text` 안에 있다.

```json
{
  "type": "say",
  "say": "completion_result",
  "text": "```json\n{\"tags\":[\"BART\"]}\n```"
}
```

`text` 값은 stringified JSON이며, ` ```json ... ``` ` fence가 붙을 수도 있고 붙지 않을 수도 있다. `kb-api enrich`는 이 message를 찾아 fence를 제거한 뒤 JSON dict로 파싱한다.

정상 출력 예:

```json
{
  "tags": ["project/project-a", "회의록"],
  "llm_tags": ["개발환경"],
  "llm_summary": "ProjectA 개발환경 회의록을 공유한 이메일."
}
```

허용되지 않는 출력 예:

```json
{
  "type": "email",
  "subject": "원본 제목",
  "conversation_id": "made-up-or-copied",
  "tags": ["회의록"]
}
```

`type`, `subject`, `from`, `conversation_id` 같은 값은 raw Markdown의 원본 metadata다. LLM이 이 값을 출력하면 `kb-api enrich`는 원본 metadata 수정 시도로 보고 reject한다.

## Cache 파일로 저장

Cline 출력이 정상 JSON인지 확인한 뒤 cache 파일에 저장한다. Cline의 raw event stream 전체가 아니라 `completion_result.text` 안의 JSON object만 cache에 저장해야 한다.

```bash
mkdir -p "$(dirname "$CACHE_FILE")"

cline --json "$(cat <<EOF
Return exactly one JSON object with only these optional keys: tags, llm_tags, llm_summary.
Do not include source metadata such as type, source, subject, from, to, dates, source_id, message_id, conversation_id, attachments, or folder.
Use evidence from this raw Markdown only.

$(cat "$RAW_FILE")
EOF
)"
```

출력 중 `type=say`, `say=completion_result`인 message의 `text` 값을 JSON으로 정리해 cache에 저장한다.

예:

```bash
cat > "$CACHE_FILE" <<'EOF'
{
  "tags": ["project/project-a", "회의록"],
  "llm_tags": ["개발환경"],
  "llm_summary": "ProjectA 개발환경 회의록을 공유한 이메일."
}
EOF
```

저장된 JSON을 확인한다.

```bash
cat "$CACHE_FILE"
```

## kb-api로 검증

cache 파일만 사용해서 Cline 호출 없이 enriched Markdown 생성을 검증한다.

```bash
kb-api enrich --file "$REL_PATH" --use-cache-only --verbose
```

성공하면 `enriched_vault_path` 아래 같은 상대 경로에 결과 파일이 생성된다.

```text
KnowledgeVault-Enriched/20_Emails/ProjectA/example.md
```

실패하면 stderr의 `ENRICH_FAILED` 로그를 본다.

```text
ENRICH_FAILED action=skip rel=20_Emails/ProjectA/example.md stage=render_enriched_markdown error_type=ValueError ...
```

자주 보는 원인:

- `type`, `subject`, `conversation_id` 같은 source metadata가 Cline output에 포함됨
- JSON 문법 오류
- Cline event stream 전체를 cache에 저장함. cache에는 `completion_result.text` 안의 metadata JSON object만 저장해야 한다.
- cache 파일이 raw 파일 상대 경로와 맞지 않음
- tag 값이 허용된 taxonomy 형식이 아님

## 운영 팁

대형 vault에서는 먼저 파일 하나로 이 절차를 통과시킨 뒤 전체 enrich를 실행한다.

```bash
kb-api enrich --file "$REL_PATH" --verbose
kb-api enrich
```
