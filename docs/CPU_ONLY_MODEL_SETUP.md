# CPU-only Model Setup for Linux

이 문서는 `kb-api`에 CPU-only enrichment provider를 추가하기 전에 Linux에서 어떤 모델을 설치하고, 어떻게 테스트하고, 나중에 `kb-api`가 어떻게 사용할지 설명한다.

초보자 기준으로 작성했다. 그대로 따라 하면 모델 실행 환경과 모델 cache가 준비된다. 그 다음 단계로 provider 코드를 추가하면 된다.

## 결론

`llm_tags`와 `llm_summary`에는 다음 모델을 사용한다.

| 목적 | 결정 모델 | 이유 |
| --- | --- | --- |
| `llm_tags` | `monologg/koelectra-small-finetuned-naver-ner` | 한국어 NER token classification 모델이고 13.7M parameter라 CPU에서 가볍다. 사람, 기관, 장소 같은 보조 tag 후보 추출에 적합하다. |
| `llm_summary` | `gogamza/kobart-summarization` | 한국어 요약용 KoBART 모델이고 0.1B parameter급이다. T5-base보다 가벼워 CPU batch enrichment 기본 모델로 쓰기 좋다. |

중요한 제한도 있다.

- `monologg/koelectra-small-finetuned-naver-ner`는 주제 tag를 똑똑하게 만들어주는 모델이 아니다. 사람, 기관, 장소 같은 이름을 찾아 `llm_tags` 후보로 쓰는 모델이다.
- `gogamza/kobart-summarization`은 뉴스 요약 계열 모델이다. 이메일과 업무 노트에서는 품질 검증이 필요하고, 짧은 문서나 실패 케이스에는 extractive fallback이 있어야 한다.
- `tags`는 별도 모델보다 taxonomy/rule 기반으로 만드는 것이 맞다. 이 문서는 `llm_tags`, `llm_summary` 준비에 집중한다.

모델 정보는 2026-05-21에 Hugging Face 모델 페이지를 확인했다.

- `monologg/koelectra-small-finetuned-naver-ner`: https://huggingface.co/monologg/koelectra-small-finetuned-naver-ner
- `gogamza/kobart-summarization`: https://huggingface.co/gogamza/kobart-summarization

## 전체 그림

나중에 provider가 추가되면 `kb-api enrich`는 대략 이렇게 동작한다.

```text
raw Markdown
  -> CpuMetadataProvider.generate_metadata(raw_markdown)
    -> NER model로 사람/기관/장소 후보 추출
    -> keyword rule로 보조 tag 후보 정리
    -> KoBART model로 짧은 요약 생성
    -> {"llm_tags": [...], "llm_summary": "..."} 반환
  -> 기존 validate_llm_metadata()
  -> 기존 render_enriched_markdown()
  -> enriched Markdown 저장
```

즉, 모델은 provider 내부에서만 쓰인다. 기존 `enrichment.py`의 cache, validation, Markdown writing 흐름은 그대로 유지한다.

## 1. Linux 준비

먼저 repository root로 이동한다.

```bash
cd /path/to/kbkb
```

Python version을 확인한다. 이 프로젝트는 Python 3.11 이상을 요구한다.

```bash
python3 --version
```

예상 출력은 이런 형태다.

```text
Python 3.11.x
```

아직 virtual environment가 없다면 만든다.

```bash
python3 -m venv .venv
```

활성화한다.

```bash
source .venv/bin/activate
```

이제 command prompt 앞에 `(.venv)` 같은 표시가 보이면 된다.

## 2. kbkb 기본 설치

먼저 현재 프로젝트를 editable mode로 설치한다.

```bash
python -m pip install -U pip
python -m pip install -e ".[api]"
```

설치 확인:

```bash
kb-api --help
```

`kb-api` help가 출력되면 기본 설치는 끝났다.

## 3. CPU 모델 실행용 패키지 설치

PyTorch CPU wheel을 설치한다.

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Hugging Face 모델 실행에 필요한 패키지를 설치한다.

```bash
python -m pip install transformers sentencepiece safetensors
```

설치 확인:

```bash
python - <<'PY'
import torch
import transformers

print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda available", torch.cuda.is_available())
PY
```

CPU-only Linux에서는 `cuda available False`가 정상이다.

## 4. 모델 cache 위치 정하기

Hugging Face 모델은 처음 실행할 때 인터넷에서 다운로드되고, 이후에는 local cache에서 재사용된다.

기본 cache는 보통 `~/.cache/huggingface`다. 명시적으로 정하고 싶으면 다음을 shell 설정에 넣는다.

```bash
export HF_HOME="$HOME/.cache/huggingface"
```

현재 shell에서 바로 적용하려면:

```bash
mkdir -p "$HOME/.cache/huggingface"
export HF_HOME="$HOME/.cache/huggingface"
```

systemd service에서 provider를 실행할 계획이면 나중에 service environment에도 같은 값을 넣는 것이 좋다.

## 5. `llm_tags` 모델 다운로드와 테스트

이 단계는 `monologg/koelectra-small-finetuned-naver-ner`가 Linux CPU에서 로드되는지 확인한다.

```bash
python - <<'PY'
from transformers import pipeline

model_name = "monologg/koelectra-small-finetuned-naver-ner"
ner = pipeline(
    "token-classification",
    model=model_name,
    tokenizer=model_name,
    aggregation_strategy="simple",
    device=-1,
)

text = "김민수 매니저가 카카오 판교오피스에서 SSO 장애 회의록을 공유했습니다."
items = ner(text)

print("model:", model_name)
for item in items:
    print(item)
PY
```

처음 실행은 모델 다운로드 때문에 오래 걸릴 수 있다. 두 번째부터는 cache를 사용해서 빨라진다.

provider에서는 이 결과를 그대로 tag로 쓰지 않는다. 다음처럼 후처리해야 한다.

1. entity text를 꺼낸다.
2. 너무 짧은 값, 숫자만 있는 값, 이메일 주소 같은 값은 버린다.
3. `_normalize_tag()`가 허용하는 형태로 바꾼다.
4. 최대 20개 제한에 맞춘다.

예시:

```text
"카카오" -> "카카오"
"판교오피스" -> "판교오피스"
```

이 값들은 `llm_tags`에만 넣는 것이 좋다. `tags`는 검색 필터용 정규 taxonomy여야 하므로 NER 결과를 바로 넣으면 tag 체계가 지저분해질 수 있다.

## 6. `llm_summary` 모델 다운로드와 테스트

이 단계는 `gogamza/kobart-summarization`이 Linux CPU에서 로드되는지 확인한다.

```bash
python - <<'PY'
import torch
from transformers import PreTrainedTokenizerFast, BartForConditionalGeneration

model_name = "gogamza/kobart-summarization"
tokenizer = PreTrainedTokenizerFast.from_pretrained(model_name)
model = BartForConditionalGeneration.from_pretrained(model_name)
model.eval()

text = (
    "오늘 오전 SSO 로그인 장애가 발생했습니다. "
    "영향 범위는 사내 업무 시스템 일부였고, 인증 서버 재시작 후 복구되었습니다. "
    "재발 방지를 위해 모니터링 알림 기준을 조정하고 장애 회고 회의를 진행하기로 했습니다."
)

raw_input_ids = tokenizer.encode(text)
input_ids = [tokenizer.bos_token_id] + raw_input_ids[:768] + [tokenizer.eos_token_id]

with torch.no_grad():
    summary_ids = model.generate(
        torch.tensor([input_ids]),
        max_length=96,
        min_length=12,
        num_beams=4,
        no_repeat_ngram_size=3,
        early_stopping=True,
    )

summary = tokenizer.decode(summary_ids.squeeze().tolist(), skip_special_tokens=True)
print("model:", model_name)
print(summary)
PY
```

요약 문장이 출력되면 모델 실행은 성공이다.

provider에서는 입력이 너무 길 때 전체 Markdown을 그대로 넣으면 안 된다. CPU에서 느리고, 모델 입력 길이도 제한된다.

권장 입력 구성:

1. frontmatter는 요약 입력에서 제거한다.
2. 제목, subject, 첫 본문 문단을 우선 넣는다.
3. 긴 문서는 문장 단위로 잘라 중요한 문장 몇 개만 고른다.
4. tokenizer 기준 768 token 정도로 자른다.
5. 결과가 비어 있거나 이상하면 첫 의미 있는 문장 1~2개를 fallback summary로 쓴다.

## 7. 모델 파일이 다운로드되었는지 확인

cache directory를 확인한다.

```bash
find "$HF_HOME" -maxdepth 4 -type d | grep -E 'koelectra|kobart|models--monologg|models--gogamza' | head
```

아무 것도 안 보이면 기본 cache를 쓰고 있을 수 있다.

```bash
find "$HOME/.cache/huggingface" -maxdepth 4 -type d | grep -E 'koelectra|kobart|models--monologg|models--gogamza' | head
```

## 8. kb-api에서 어떻게 쓰게 될지

현재 시점에서는 모델 설치만으로 `kb-api enrich`가 자동으로 바뀌지 않는다. 지금 기본 provider는 `ClineCliMetadataProvider`다.

provider를 추가한 뒤에는 이런 형태가 된다.

```python
class CpuMetadataProvider:
    def __init__(self):
        self.ner = load_ner_model_once()
        self.summarizer = load_kobart_once()

    def generate_metadata(self, raw_markdown: str) -> dict[str, object]:
        text = strip_frontmatter(raw_markdown)
        llm_tags = extract_llm_tags_with_ner(self.ner, text)
        llm_summary = summarize_with_kobart(self.summarizer, text)
        return {
            "llm_tags": llm_tags,
            "llm_summary": llm_summary,
        }
```

그리고 `enrich_vault()`가 provider를 선택할 수 있어야 한다.

예상 config:

```yaml
enrichment_provider: "cpu"
cpu_enrichment:
  llm_tags_model: "monologg/koelectra-small-finetuned-naver-ner"
  llm_summary_model: "gogamza/kobart-summarization"
  device: "cpu"
  max_summary_input_tokens: 768
```

예상 command:

```bash
kb-api enrich --config ~/.config/kb-api/config.yaml
```

이때 CPU provider가 cache miss인 파일만 처리하고, 결과를 기존 enrichment cache에 JSON으로 저장하게 만들면 된다.

예상 cache JSON:

```json
{
  "llm_tags": ["카카오", "판교오피스"],
  "llm_summary": "SSO 로그인 장애가 발생했고 인증 서버 재시작 후 복구되었으며 재발 방지 조치를 진행하기로 했다."
}
```

기존 `validate_llm_metadata()`와 `render_enriched_markdown()`은 이 JSON을 이미 받아들일 수 있다.

## 9. provider 추가 전에 꼭 확인할 것

모델 설치 후 다음 3가지를 확인한다.

```bash
python -m unittest discover -s tests -v
```

```bash
python - <<'PY'
from transformers import pipeline
pipeline("token-classification", model="monologg/koelectra-small-finetuned-naver-ner", device=-1)
print("NER OK")
PY
```

```bash
python - <<'PY'
from transformers import PreTrainedTokenizerFast, BartForConditionalGeneration
PreTrainedTokenizerFast.from_pretrained("gogamza/kobart-summarization")
BartForConditionalGeneration.from_pretrained("gogamza/kobart-summarization")
print("KoBART OK")
PY
```

셋 다 성공하면 provider 추가 준비가 끝난 것이다.

## 10. 자주 막히는 문제

### `Could not resolve host` 또는 download 실패

Linux machine이 Hugging Face에 접속할 수 없는 상태다. 인터넷이 되는 환경에서 한 번 모델을 다운로드하거나, cache directory를 다른 machine에서 복사해야 한다.

### 실행이 너무 느림

CPU에서는 정상일 수 있다. provider 구현 시 다음을 지켜야 한다.

- 파일마다 모델을 새로 로드하지 않는다.
- 프로세스 시작 시 한 번만 모델을 로드한다.
- 긴 문서는 tokenizer 입력 길이를 제한한다.
- cache hit 파일은 모델을 호출하지 않는다.

### memory가 부족함

`gogamza/kobart-summarization`은 0.1B parameter급이라 비교적 작지만, CPU RAM이 아주 작으면 부담이 될 수 있다.

대안:

- summary를 extractive fallback으로 먼저 구현한다.
- KoBART는 특정 folder에만 적용한다.
- batch 크기를 1로 유지한다.

### 생성 요약이 이상함

뉴스 요약 모델이라 업무 메일에서는 어색할 수 있다. provider에 fallback을 반드시 넣는다.

권장 fallback:

1. 본문 첫 1~2개 의미 있는 문장
2. subject + 첫 문장
3. 너무 짧으면 summary key를 생략

## 이 문서를 따라한 뒤 provider를 추가하면 되는가?

맞다. 이 문서는 provider 구현 전에 필요한 Linux 실행 환경과 모델 cache를 준비하는 단계다.

다만 이것만으로 `kb-api enrich`가 CPU 모델을 쓰지는 않는다. 다음 코드 작업이 추가로 필요하다.

1. `CpuMetadataProvider` 추가
2. provider 선택 config 또는 CLI option 추가
3. NER 결과를 `llm_tags`로 바꾸는 후처리
4. KoBART 결과를 `llm_summary`로 바꾸는 요약 wrapper
5. cache miss일 때만 모델을 호출하도록 기존 cache 흐름에 연결
6. 작은 fixture로 `validate_llm_metadata()` 통과 테스트 추가

이 작업까지 끝나면 사용자는 `kb-api enrich`를 그대로 실행하되, 내부 provider만 CPU 모델 기반으로 바꿀 수 있다.
