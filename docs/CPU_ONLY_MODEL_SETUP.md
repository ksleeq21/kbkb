# CPU-only Model Setup for Linux

이 문서는 `kb-api`에 CPU-only enrichment provider를 추가하기 전에 Linux에서 모델 파일을 준비하고, 외부 요청 없이 local CPU로 테스트하는 방법을 설명한다.

초보자 기준으로 작성했다. 그대로 따라 하면 운영 Linux machine에는 모델 파일이 local directory로 배치되고, 테스트 실행 중 Hugging Face Hub로 요청을 보내지 않게 된다. 그 다음 단계로 provider 코드를 추가하면 된다.

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

## 왜 오프라인 방식인가

Hugging Face의 `pipeline(..., model="monologg/...")` 또는 `from_pretrained("gogamza/...")`처럼 모델 이름을 바로 넘기면, 처음 실행할 때 Python library가 `huggingface.co`에 `HEAD`/`GET` 요청을 보내 모델 파일을 확인하고 다운로드한다.

회사망, 보안망, proxy 환경에서는 이때 다음 오류가 날 수 있다.

```text
ssl: certificate_verify_failed
self-signed certificate in certificate chain
```

이 오류는 모델 추론이 실패했다는 뜻이 아니라, 모델 파일을 받으러 가는 HTTPS 연결의 인증서 검증이 실패했다는 뜻이다. 입력 문장을 Hugging Face inference API로 보내는 구조는 아니지만, 모델 파일이 local에 없으면 Hub에 접속하려고 한다.

운영에서는 이 동작을 피하는 편이 좋다.

- 모델 파일은 미리 다운로드한다.
- 운영 Linux에는 모델 directory를 복사한다.
- 실행 시 `HF_HUB_OFFLINE=1`을 켠다.
- 코드에서는 모델 이름 대신 local path를 넘기고 `local_files_only=True`를 사용한다.

공식 Transformers 문서도 firewalled/offline 환경에서는 `HF_HUB_OFFLINE=1` 또는 `local_files_only=True`를 사용하라고 안내한다.

## 전체 그림

나중에 provider가 추가되면 `kb-api enrich`는 대략 이렇게 동작한다.

```text
raw Markdown
  -> CpuMetadataProvider.generate_metadata(raw_markdown)
    -> local NER model directory로 사람/기관/장소 후보 추출
    -> keyword rule로 보조 tag 후보 정리
    -> local KoBART model directory로 짧은 요약 생성
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

운영 Linux에서 모델을 실행하려면 PyTorch와 Transformers가 필요하다. 이 단계는 package 설치라 인터넷 또는 내부 PyPI mirror가 필요할 수 있다.

PyTorch CPU wheel을 설치한다.

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Hugging Face 모델 실행에 필요한 패키지를 설치한다.

```bash
python -m pip install transformers sentencepiece safetensors huggingface_hub
```

설치 확인:

```bash
python - <<'PY'
import torch
import transformers
import huggingface_hub

print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("huggingface_hub", huggingface_hub.__version__)
print("cuda available", torch.cuda.is_available())
PY
```

CPU-only Linux에서는 `cuda available False`가 정상이다.

## 4. 모델 directory 정하기

운영 Linux에서는 모델을 cache 이름이 아니라 명시적인 directory로 관리하는 편이 이해하기 쉽다.

권장 위치:

```bash
mkdir -p "$HOME/.local/share/kb-api/models"
```

이 문서에서는 다음 두 directory를 사용한다.

```text
$HOME/.local/share/kb-api/models/koelectra-ner
$HOME/.local/share/kb-api/models/kobart-summarization
```

systemd service로 실행할 계획이면 service user가 이 directory를 읽을 수 있어야 한다.

## 5. 모델 파일 준비 방법 선택

모델 파일을 준비하는 방법은 두 가지다.

### 방법 A: 인터넷이 되는 staging machine에서 다운로드 후 복사

운영 Linux가 외부 접속이나 SSL 인증서 문제로 Hugging Face에 접근할 수 없다면 이 방법을 추천한다.

인터넷이 되는 machine에서 실행한다.

```bash
python3 -m venv hf-download-venv
source hf-download-venv/bin/activate
python -m pip install -U pip
python -m pip install huggingface_hub
```

모델을 local folder로 다운로드한다.

```bash
mkdir -p ./kb-api-models

python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="monologg/koelectra-small-finetuned-naver-ner",
    local_dir="./kb-api-models/koelectra-ner",
    local_dir_use_symlinks=False,
)

snapshot_download(
    repo_id="gogamza/kobart-summarization",
    local_dir="./kb-api-models/kobart-summarization",
    local_dir_use_symlinks=False,
)
PY
```

그 다음 `kb-api-models` folder를 운영 Linux로 복사한다. 예시는 `scp`다.

```bash
scp -r ./kb-api-models/koelectra-ner your-linux-user@your-linux-host:~/.local/share/kb-api/models/
scp -r ./kb-api-models/kobart-summarization your-linux-user@your-linux-host:~/.local/share/kb-api/models/
```

운영 Linux에서 확인한다.

```bash
ls -la "$HOME/.local/share/kb-api/models/koelectra-ner"
ls -la "$HOME/.local/share/kb-api/models/kobart-summarization"
```

### 방법 B: 운영 Linux에서 한 번만 온라인 다운로드

운영 Linux가 Hugging Face에 정상 접속할 수 있다면 직접 다운로드해도 된다. SSL 에러가 난 환경에서는 이 방법이 실패할 수 있다.

```bash
mkdir -p "$HOME/.local/share/kb-api/models"

python - <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path

model_root = Path.home() / ".local/share/kb-api/models"

snapshot_download(
    repo_id="monologg/koelectra-small-finetuned-naver-ner",
    local_dir=model_root / "koelectra-ner",
    local_dir_use_symlinks=False,
)

snapshot_download(
    repo_id="gogamza/kobart-summarization",
    local_dir=model_root / "kobart-summarization",
    local_dir_use_symlinks=False,
)
PY
```

다운로드가 끝난 뒤부터는 offline mode로 실행한다.

## 6. 오프라인 mode 켜기

운영 Linux에서 외부 요청을 막으려면 다음 환경 변수를 설정한다.

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

현재 shell에서만 적용된다. systemd service로 실행할 때는 service file 또는 environment file에도 넣는다.

예:

```ini
Environment=HF_HUB_OFFLINE=1
Environment=TRANSFORMERS_OFFLINE=1
```

provider 코드에서도 `local_files_only=True`를 사용해야 한다. 환경 변수와 코드 옵션을 둘 다 쓰면 실수로 Hub에 접속하는 것을 더 확실히 막을 수 있다.

## 7. `llm_tags` 모델 오프라인 테스트

이 단계는 `monologg/koelectra-small-finetuned-naver-ner`가 local directory에서 CPU로 로드되는지 확인한다.

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export KB_API_NER_MODEL="$HOME/.local/share/kb-api/models/koelectra-ner"

python - <<'PY'
import os
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

model_path = os.environ["KB_API_NER_MODEL"]

tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForTokenClassification.from_pretrained(model_path, local_files_only=True)

ner = pipeline(
    "token-classification",
    model=model,
    tokenizer=tokenizer,
    aggregation_strategy="simple",
    device=-1,
)

text = "김민수 매니저가 카카오 판교오피스에서 SSO 장애 회의록을 공유했습니다."
items = ner(text)

print("model path:", model_path)
for item in items:
    print(item)
PY
```

이 명령은 모델 이름이 아니라 local path를 사용한다. 모델 파일이 모두 준비되어 있으면 Hugging Face Hub로 요청하지 않는다.

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

## 8. `llm_summary` 모델 오프라인 테스트

이 단계는 `gogamza/kobart-summarization`이 local directory에서 CPU로 로드되는지 확인한다.

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export KB_API_SUMMARY_MODEL="$HOME/.local/share/kb-api/models/kobart-summarization"

python - <<'PY'
import os
import torch
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast

model_path = os.environ["KB_API_SUMMARY_MODEL"]

tokenizer = PreTrainedTokenizerFast.from_pretrained(model_path, local_files_only=True)
model = BartForConditionalGeneration.from_pretrained(model_path, local_files_only=True)
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
print("model path:", model_path)
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

## 9. 외부 요청이 없는지 확인하기

가장 중요한 확인은 모델 이름이 아니라 local path를 쓰는 것이다.

좋은 예:

```python
AutoTokenizer.from_pretrained("/home/you/.local/share/kb-api/models/koelectra-ner", local_files_only=True)
```

피해야 할 예:

```python
AutoTokenizer.from_pretrained("monologg/koelectra-small-finetuned-naver-ner")
```

offline mode가 켜져 있는지도 확인한다.

```bash
python - <<'PY'
import os

print("HF_HUB_OFFLINE=", os.environ.get("HF_HUB_OFFLINE"))
print("TRANSFORMERS_OFFLINE=", os.environ.get("TRANSFORMERS_OFFLINE"))
PY
```

둘 다 `1`이면 된다.

더 강하게 확인하고 싶으면 네트워크가 막힌 상태에서 7번과 8번 테스트를 실행한다. 성공하면 local file만 사용한 것이다.

## 10. kb-api에서 어떻게 쓰게 될지

현재 시점에서는 모델 설치만으로 `kb-api enrich`가 자동으로 바뀌지 않는다. 지금 기본 provider는 `ClineCliMetadataProvider`다.

provider를 추가한 뒤에는 이런 형태가 된다.

```python
class CpuMetadataProvider:
    def __init__(self, ner_model_path: str, summary_model_path: str):
        self.ner = load_ner_model_once(ner_model_path, local_files_only=True)
        self.summarizer = load_kobart_once(summary_model_path, local_files_only=True)

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
  llm_tags_model_path: "/home/you/.local/share/kb-api/models/koelectra-ner"
  llm_summary_model_path: "/home/you/.local/share/kb-api/models/kobart-summarization"
  device: "cpu"
  offline: true
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

## 11. provider 추가 전에 꼭 확인할 것

모델 설치 후 다음 3가지를 확인한다.

```bash
python -m unittest discover -s tests -v
```

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export KB_API_NER_MODEL="$HOME/.local/share/kb-api/models/koelectra-ner"

python - <<'PY'
import os
from transformers import AutoModelForTokenClassification, AutoTokenizer

model_path = os.environ["KB_API_NER_MODEL"]
AutoTokenizer.from_pretrained(model_path, local_files_only=True)
AutoModelForTokenClassification.from_pretrained(model_path, local_files_only=True)
print("NER OK")
PY
```

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export KB_API_SUMMARY_MODEL="$HOME/.local/share/kb-api/models/kobart-summarization"

python - <<'PY'
import os
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast

model_path = os.environ["KB_API_SUMMARY_MODEL"]
PreTrainedTokenizerFast.from_pretrained(model_path, local_files_only=True)
BartForConditionalGeneration.from_pretrained(model_path, local_files_only=True)
print("KoBART OK")
PY
```

셋 다 성공하면 provider 추가 준비가 끝난 것이다.

## 12. 자주 막히는 문제

### `self-signed certificate in certificate chain`

모델 이름을 사용해서 Hugging Face에 접속하려다가 SSL 인증서 검증이 실패한 것이다.

해결:

- 운영 Linux에서는 local model path를 사용한다.
- `HF_HUB_OFFLINE=1`과 `TRANSFORMERS_OFFLINE=1`을 설정한다.
- `from_pretrained(..., local_files_only=True)`를 사용한다.
- 모델 파일은 인터넷이 되는 staging machine에서 미리 다운로드한 뒤 복사한다.

### `cannot send a request, as the client has been closed`

대개 앞선 SSL 실패 후 내부 HTTP client가 닫힌 상태에서 추가 요청이 발생하며 따라오는 2차 오류다. 먼저 SSL 실패 또는 온라인 접속 시도를 없애야 한다.

### `Cannot find the requested files in the disk cache`

offline mode는 켜져 있는데 local model directory에 필요한 파일이 없다.

확인:

```bash
ls -la "$HOME/.local/share/kb-api/models/koelectra-ner"
ls -la "$HOME/.local/share/kb-api/models/kobart-summarization"
```

필요한 파일이 없다면 5번의 모델 준비 단계를 다시 수행한다.

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

맞다. 이 문서는 provider 구현 전에 필요한 Linux 실행 환경과 local model directory를 준비하는 단계다.

다만 이것만으로 `kb-api enrich`가 CPU 모델을 쓰지는 않는다. 다음 코드 작업이 추가로 필요하다.

1. `CpuMetadataProvider` 추가
2. provider 선택 config 또는 CLI option 추가
3. NER 결과를 `llm_tags`로 바꾸는 후처리
4. KoBART 결과를 `llm_summary`로 바꾸는 요약 wrapper
5. cache miss일 때만 모델을 호출하도록 기존 cache 흐름에 연결
6. `local_files_only=True`와 offline mode를 provider에서 지원
7. 작은 fixture로 `validate_llm_metadata()` 통과 테스트 추가

이 작업까지 끝나면 사용자는 `kb-api enrich`를 그대로 실행하되, 내부 provider만 local CPU 모델 기반으로 바꿀 수 있다.
