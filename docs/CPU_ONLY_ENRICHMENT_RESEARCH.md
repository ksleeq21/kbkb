# CPU-only Enrichment Research

이 문서는 현재 `kb_api/enrichment.py`의 enrichment 방식을 정리하고, Cline/LLM API 비용 없이 CPU만으로 한국어 문서를 태깅하고 요약하는 대체 방식을 제안한다.

## 현재 Enrichment 방식

현재 enrichment는 `kb_api.enrichment.enrich_vault()`가 raw Markdown vault를 스캔하고, 각 Markdown마다 `MetadataProvider.generate_metadata(raw_markdown)`를 호출해 metadata JSON을 만든 뒤, 이를 enriched Markdown frontmatter에 병합하는 구조다.

핵심 흐름은 다음과 같다.

1. `raw_vault_path`에서 Markdown 파일을 선택한다.
2. 전체 실행이면 Markdown이 아닌 파일을 `enriched_vault_path`로 복사한다.
3. 각 Markdown에 대해 cache 파일 `<relative>.metadata.json`이 있으면 재사용한다.
4. cache가 없고 `--use-cache-only`가 아니면 기본 provider인 `ClineCliMetadataProvider`를 호출한다.
5. provider 결과를 cache에 저장한다.
6. `render_enriched_markdown()`이 raw frontmatter를 보존하면서 허용된 metadata만 병합한다.
7. enriched Markdown을 raw vault와 같은 상대 경로로 쓴다.

현재 provider 계약은 `kb_api/enrichment_providers.py`의 `MetadataProvider` protocol이다. 즉, 대체 구현은 `generate_metadata(raw_markdown: str) -> dict[str, Any]`만 맞추면 기존 vault/cache/render 흐름을 그대로 재사용할 수 있다.

현재 허용되는 provider 출력 key는 다음 3개뿐이다.

```json
{
  "tags": ["정규화된-검색-tag"],
  "llm_tags": ["보조-tag"],
  "llm_summary": "짧은 요약"
}
```

`validate_llm_metadata()`는 원본 source metadata 수정을 금지하고, `tags`와 `llm_tags`를 최대 20개로 제한하며, tag 값을 `_normalize_tag()` 규칙으로 정규화한다. 따라서 CPU-only provider도 source metadata를 만들지 말고 위 key만 반환해야 한다.

## 목표

LLM API를 쓰지 않고 CPU에서 다음 enrichment를 만든다.

- `tags`: 검색과 필터에 쓰는 안정적인 정규화 tag
- `llm_tags`: 문서에서 추출한 보조 keyword/tag
- `llm_summary`: 검색 결과와 문서 목록에서 확인 가능한 짧은 한국어 요약

비용 절감이 목적이므로 모델 품질만이 아니라 CPU 추론 속도, 배치 처리 가능성, dependency 크기, 실패 시 fallback이 중요하다.

## 권장 아키텍처

### 1. Tagging은 생성보다 선택으로 바꾼다

현재 문서에도 tag taxonomy가 필요하다고 정리되어 있다. CPU-only에서는 LLM처럼 자유롭게 tag를 생성시키기보다, repo나 설정 파일에 taxonomy를 두고 문서를 후보 tag에 매칭하는 방식이 더 안정적이다.

권장 pipeline:

1. raw Markdown에서 frontmatter, 제목, 본문, 첨부 파일명, 폴더 path를 분리한다.
2. 기존 folder tag와 raw tag는 그대로 유지한다.
3. taxonomy 항목마다 alias/keyword를 둔다.
4. exact/regex match로 높은 확신 tag를 먼저 붙인다.
5. 남는 후보는 embedding similarity 또는 zero-shot classification으로 점수화한다.
6. threshold 이상인 tag만 `tags`에 넣고, 추출 keyword는 `llm_tags`에 넣는다.

이 방식은 같은 의미의 tag가 갈라지는 문제를 줄이고, `tags_json LIKE` 기반의 현재 검색 필터에도 잘 맞는다.

### 2. Keyword/tag 후보 추출은 규칙 + embedding이 현실적이다

한국어 keyphrase extraction 전용 Hugging Face 모델은 영어권 모델보다 선택지가 적고, 범용 keyphrase 모델은 대개 영어 데이터셋 기반이다. 따라서 한국어 vault에는 다음 조합이 더 실용적이다.

- 형태소 분석 또는 간단한 명사구 추출로 후보 생성
- 빈도, 제목/subject 가중치, 폴더명/첨부파일명 가중치로 후보 ranking
- 한국어 sentence embedding으로 taxonomy alias와 후보 phrase를 비교

추천 embedding 모델:

- [`jhgan/ko-sroberta-multitask`](https://huggingface.co/jhgan/ko-sroberta-multitask)
  - Korean sentence-transformers 모델이다.
  - 문장/문단을 768차원 벡터로 매핑하며 clustering이나 semantic search에 사용할 수 있다고 모델 카드가 설명한다.
  - `sentence-transformers`, Transformers, ONNX, OpenVINO 사용 경로가 있어 CPU 운영에 맞다.
  - 모델 카드 기준 max sequence length가 128이라 긴 문서 전체보다 제목, 첫 문단, 문장 chunk, 후보 phrase 매칭에 쓰는 편이 적합하다.

초경량 tagging 후보:

- [`monologg/koelectra-small-finetuned-naver-ner`](https://huggingface.co/monologg/koelectra-small-finetuned-naver-ner)
  - 13.7M parameter token classification 모델이다.
  - 사람/기관/장소 등 NER 성격의 tag 보조에는 가볍지만, 프로젝트/업무 주제 tag를 직접 만들기에는 한계가 있다.

Zero-shot 후보:

- [`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7)
  - 27개 언어 지원 zero-shot classification 모델이다.
  - taxonomy 후보가 적을 때는 "이 문서는 {tag 설명}에 관한 문서다" 형태로 후보를 score할 수 있다.
  - CPU에서는 후보 tag 수만큼 sequence classification을 반복하므로 embedding 방식보다 느릴 가능성이 높다.

추천 결론: `tags`는 taxonomy rule + `jhgan/ko-sroberta-multitask` similarity로 만들고, NER는 `llm_tags` 보조 신호로만 사용한다. zero-shot은 초기 taxonomy가 빈약할 때의 보조 옵션으로 둔다.

### 3. 요약은 KoBART 또는 T5, 긴 문서는 chunk 요약

한국어 요약 모델 후보:

- [`gogamza/kobart-summarization`](https://huggingface.co/gogamza/kobart-summarization)
  - Korean news summarization model로 공개되어 있다.
  - 0.1B parameter급이고 MIT license다.
  - CPU에서 T5-base보다 가볍고, 짧은 이메일/노트 요약에 가장 현실적인 기본 후보다.

- [`digit82/kobart-summarization`](https://huggingface.co/digit82/kobart-summarization)
  - 다운로드 수가 많고 사용 예제가 단순하지만, 모델 카드가 거의 없다.
  - 운영 모델로 채택하기 전에는 sample vault에서 품질과 license/출처 리스크를 확인해야 한다.

- [`ainize/kobart-news`](https://huggingface.co/ainize/kobart-news)
  - KoBART를 AI Hub 문서요약 텍스트/신문기사 데이터로 fine-tune한 모델이라고 모델 카드가 설명한다.
  - 뉴스성 문서에는 적합하지만, 이메일/회의록/업무 노트에 대한 도메인 차이를 검증해야 한다.

- [`eenzeenee/t5-base-korean-summarization`](https://huggingface.co/eenzeenee/t5-base-korean-summarization)
  - 한국어 요약용 T5 model이며 논문자료, 도서자료, 요약문/레포트 생성 데이터로 fine-tune되었다고 설명되어 있다.
  - 0.3B parameter라 CPU 비용이 KoBART보다 높다.
  - 긴 보고서류에는 후보가 될 수 있지만, 대량 vault batch enrichment 기본값으로는 무겁다.

추천 결론: 기본 summarizer는 `gogamza/kobart-summarization`을 먼저 평가한다. 긴 보고서/문서 폴더에만 `eenzeenee/t5-base-korean-summarization`을 선택적으로 쓰는 2-tier 구성이 좋다.

## 최종 추천 모델 조합

1. `tags`: rule/taxonomy first
   - 모델 없이 folder, source metadata, subject, filename, attachment name, regex alias로 high-confidence tag를 붙인다.
   - 가장 싸고 deterministic하다.

2. `tags` 보강: `jhgan/ko-sroberta-multitask`
   - taxonomy label/alias embedding을 미리 계산한다.
   - 문서 제목, subject, 첫 1~3개 문단, 상위 keyword 후보를 embedding해 cosine similarity로 tag를 선택한다.
   - CPU batch inference와 ONNX/OpenVINO 최적화가 가능하다.

3. `llm_tags`: lightweight keyword extraction
   - 처음에는 모델 없는 TF-IDF/RAKE류 + 한국어 stopword + 제목 가중치로 시작한다.
   - 필요하면 `monologg/koelectra-small-finetuned-naver-ner`로 사람/기관/장소 entity만 보조 tag 후보에 넣는다.

4. `llm_summary`: `gogamza/kobart-summarization`
   - 짧은 문서는 본문 앞쪽과 제목/subject를 합쳐 한 번 요약한다.
   - 긴 문서는 문장 단위 chunk를 만들고, chunk별 extractive top 문장을 고른 뒤 KoBART에 넣는다.
   - 실패하거나 입력이 너무 짧으면 첫 의미 있는 문장 1~2개를 extractive summary로 사용한다.

## 구현 제안

새 provider를 `kb_api/enrichment_providers.py`에 추가한다.

```python
class CpuMetadataProvider:
    def __init__(self, taxonomy: TagTaxonomy, summarizer: KoreanSummarizer, tagger: KoreanTagger):
        self.taxonomy = taxonomy
        self.summarizer = summarizer
        self.tagger = tagger

    def generate_metadata(self, raw_markdown: str) -> dict[str, Any]:
        document = parse_markdown(raw_markdown)
        tags = self.tagger.select_tags(document)
        llm_tags = self.tagger.extract_keywords(document)
        summary = self.summarizer.summarize(document)
        return {
            "tags": tags,
            "llm_tags": llm_tags,
            "llm_summary": summary,
        }
```

CLI/config에는 provider 선택 옵션을 추가한다.

```yaml
enrichment_provider: cpu
enrichment_taxonomy_path: "/home/you/.config/kb-api/tag-taxonomy.yaml"
cpu_enrichment:
  embedding_model: "jhgan/ko-sroberta-multitask"
  summarization_model: "gogamza/kobart-summarization"
  max_summary_input_tokens: 768
  tag_similarity_threshold: 0.58
```

초기 taxonomy 예시는 다음 형태가 좋다.

```yaml
tags:
  - name: "회의록"
    aliases: ["회의록", "미팅노트", "회의 메모", "meeting minutes"]
    patterns: ["회의록", "미팅", "agenda", "minutes"]
  - name: "장애"
    aliases: ["장애", "incident", "outage", "서비스 장애"]
    patterns: ["장애", "복구", "영향도", "incident", "outage"]
  - name: "project/project-a"
    aliases: ["ProjectA", "프로젝트 A"]
    patterns: ["ProjectA", "project-a"]
```

## 운영 전략

- 모델은 enrichment 프로세스 시작 시 1회 로드하고 파일별로 재사용한다.
- taxonomy embedding은 cache 파일로 저장한다.
- raw Markdown cache는 현재 `<relative>.metadata.json` 구조를 그대로 사용한다.
- `--use-cache-only` 계약은 유지한다.
- 모델 다운로드와 CPU 추론 dependency는 optional extra로 분리한다.
- 첫 릴리스에서는 LLM provider와 CPU provider를 둘 다 유지해 A/B 비교가 가능하게 한다.

## 검증 기준

샘플 vault 100개 정도를 대상으로 다음을 측정한다.

- tag precision: 사람이 보기에도 틀린 tag 비율
- tag recall: 검색에 필요한 주요 tag 누락 비율
- summary usefulness: 검색 결과 목록에서 문서 내용을 충분히 구분하는지
- throughput: CPU에서 파일당 평균 처리 시간
- cache hit 이후 재실행 시간
- `validate_llm_metadata()` reject 비율

성공 기준은 LLM 결과를 완전히 대체하는 것이 아니라, 검색/필터/문서 식별에 충분한 metadata를 거의 무료로 재생성하는 것이다.

## 단계별 도입안

1. `CpuMetadataProvider` skeleton과 config/CLI provider 선택만 추가한다.
2. 모델 없는 rule-based tagger와 extractive summary fallback을 먼저 넣는다.
3. taxonomy YAML과 tag normalization test fixture를 추가한다.
4. `jhgan/ko-sroberta-multitask` embedding tag scorer를 optional extra로 추가한다.
5. `gogamza/kobart-summarization` summarizer를 optional extra로 추가한다.
6. 100개 샘플에서 Cline 결과와 CPU 결과를 비교하는 evaluation script를 만든다.
7. 결과가 안정되면 기본 provider를 `cpu`로 바꾸고, LLM provider는 수동 보강용으로 남긴다.

`llm_tags`와 `llm_summary` 모델 설치 및 Linux 준비 절차는 [CPU_ONLY_MODEL_SETUP.md](CPU_ONLY_MODEL_SETUP.md)를 따른다.

## 참고 링크

- Current provider contract: `kb_api/enrichment_providers.py`
- Current vault/cache/render flow: `kb_api/enrichment.py`
- `jhgan/ko-sroberta-multitask`: https://huggingface.co/jhgan/ko-sroberta-multitask
- `gogamza/kobart-summarization`: https://huggingface.co/gogamza/kobart-summarization
- `ainize/kobart-news`: https://huggingface.co/ainize/kobart-news
- `eenzeenee/t5-base-korean-summarization`: https://huggingface.co/eenzeenee/t5-base-korean-summarization
- `monologg/koelectra-small-finetuned-naver-ner`: https://huggingface.co/monologg/koelectra-small-finetuned-naver-ner
- `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`: https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
