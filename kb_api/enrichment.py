from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kb_win_sync.simple_yaml import dump_frontmatter

from .config import ApiConfig
from .enrichment_providers import ClineCliMetadataProvider, MetadataProvider
from .frontmatter import parse_markdown
from .scanner import scan_markdown


logger = logging.getLogger(__name__)

ALLOWED_METADATA_KEYS = {"tags", "llm_tags", "llm_summary"}
TAG_PATTERN = re.compile(r"^[0-9A-Za-z가-힣][0-9A-Za-z가-힣._-]*(/[0-9A-Za-z가-힣][0-9A-Za-z가-힣._-]*)*$")
FORBIDDEN_METADATA_KEYS = {
    "type",
    "source",
    "source_id",
    "source_checksum",
    "subject",
    "from",
    "to",
    "cc",
    "received",
    "received_at",
    "sent_at",
    "conversation_id",
    "message_id",
    "message_key",
    "folder",
    "outlook_folder",
    "attachments",
    "original_msg",
    "original_msg_path",
}


@dataclass(frozen=True)
class EnrichmentStats:
    raw_notes: int = 0
    enriched_notes: int = 0
    copied_files: int = 0
    failed: int = 0


def enrich_vault(
    config: ApiConfig,
    *,
    use_cache_only: bool = False,
    cline_command: str = "cline",
    metadata_provider: MetadataProvider | None = None,
    raw_file_path: str | Path | None = None,
    verbose: bool = False,
) -> EnrichmentStats:
    raw_root = config.raw_vault_path
    enriched_root = config.enriched_vault_path or config.vault_path
    cache_root = config.enrichment_cache_path
    if raw_root is None:
        raise ValueError("raw_vault_path is required for enrichment")
    if cache_root is None:
        raise ValueError("enrichment_cache_path is required for enrichment")
    if config.attachment_policy != "copy":
        raise ValueError("attachment_policy must be 'copy'")
    raw_root = Path(raw_root)
    enriched_root = Path(enriched_root)
    cache_root = Path(cache_root)
    if not raw_root.exists() or not raw_root.is_dir():
        raise ValueError(f"raw_vault_path does not exist or is not a directory: {raw_root}")

    provider = metadata_provider or ClineCliMetadataProvider(cline_command)
    logger.debug(
        "ENRICH_START raw_root=%s enriched_root=%s cache_root=%s single_file=%s use_cache_only=%s provider=%s cline_command=%s",
        raw_root,
        enriched_root,
        cache_root,
        raw_file_path or "(all)",
        use_cache_only,
        type(provider).__name__,
        cline_command,
    )
    copied = 0 if raw_file_path is not None else _copy_non_markdown_files(raw_root, enriched_root, config.ignore_dirs)
    raw_notes = 0
    enriched_notes = 0
    failed = 0
    raw_files = [_resolve_single_raw_markdown(raw_root, raw_file_path, config.ignore_dirs)] if raw_file_path is not None else scan_markdown(raw_root, config.ignore_dirs)
    logger.debug("ENRICH_PLAN markdown_files=%s copied_files=%s", len(raw_files), copied)
    for raw_file in raw_files:
        raw_notes += 1
        rel = raw_file.relative_to(raw_root)
        stage = "load_metadata"
        try:
            logger.debug("ENRICH_FILE_START rel=%s raw=%s", rel.as_posix(), raw_file)
            metadata = _load_or_create_metadata(raw_file, cache_root / rel.with_suffix(".metadata.json"), use_cache_only, provider)
            logger.debug("ENRICH_METADATA_LOADED rel=%s keys=%s", rel.as_posix(), sorted(metadata.keys()))
            stage = "read_raw_markdown"
            raw_text = raw_file.read_text(encoding="utf-8")
            logger.debug("ENRICH_RAW_READ rel=%s chars=%s", rel.as_posix(), len(raw_text))
            stage = "render_enriched_markdown"
            enriched_text = render_enriched_markdown(raw_text, metadata)
            logger.debug("ENRICH_RENDERED rel=%s chars=%s", rel.as_posix(), len(enriched_text))
            stage = "write_enriched_markdown"
            output = enriched_root / rel
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(enriched_text, encoding="utf-8")
            enriched_notes += 1
            logger.debug("ENRICH_FILE_DONE rel=%s output=%s", rel.as_posix(), output)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            failed += 1
            logger.warning(
                "ENRICH_FAILED action=skip rel=%s stage=%s error_type=%s error=%s",
                rel.as_posix(),
                stage,
                type(exc).__name__,
                exc,
                exc_info=verbose,
            )
    logger.debug("ENRICH_DONE raw_notes=%s enriched_notes=%s copied_files=%s failed=%s", raw_notes, enriched_notes, copied, failed)
    return EnrichmentStats(raw_notes=raw_notes, enriched_notes=enriched_notes, copied_files=copied, failed=failed)


def _resolve_single_raw_markdown(raw_root: Path, raw_file_path: str | Path, ignore_dirs: list[str]) -> Path:
    rel = Path(raw_file_path)
    if rel.is_absolute() or ".." in rel.parts or str(raw_file_path).strip() == "":
        raise ValueError("--file must be a raw_vault_path-relative Markdown path")
    if rel.suffix.lower() != ".md":
        raise ValueError("--file must point to a .md file")
    if set(rel.parts) & set(ignore_dirs):
        raise ValueError("--file points inside an ignored directory")
    raw_file = raw_root / rel
    if not raw_file.exists() or not raw_file.is_file():
        raise ValueError(f"--file does not exist under raw_vault_path: {rel.as_posix()}")
    return raw_file


def render_enriched_markdown(raw_text: str, llm_metadata: dict[str, Any]) -> str:
    parsed = parse_markdown(raw_text)
    metadata = dict(parsed.metadata)
    accepted = validate_llm_metadata(llm_metadata)
    if "tags" in accepted:
        metadata["tags"] = _merge_unique(_as_string_list(metadata.get("tags", [])), accepted["tags"])
    if "llm_tags" in accepted:
        metadata["llm_tags"] = accepted["llm_tags"]
    if "llm_summary" in accepted:
        metadata["llm_summary"] = accepted["llm_summary"]
    return f"{dump_frontmatter(metadata)}\n\n{parsed.body.lstrip()}"


def validate_llm_metadata(data: dict[str, Any]) -> dict[str, Any]:
    forbidden = set(data) & FORBIDDEN_METADATA_KEYS
    if forbidden:
        raise ValueError(f"llm metadata attempted to modify source keys: {', '.join(sorted(forbidden))}")
    extra = set(data) - ALLOWED_METADATA_KEYS
    if extra:
        raise ValueError(f"unsupported llm metadata keys: {', '.join(sorted(extra))}")
    accepted: dict[str, Any] = {}
    for key in ["tags", "llm_tags"]:
        if key not in data:
            continue
        values = _as_string_list(data[key])
        if len(values) > 20:
            raise ValueError(f"{key} must contain at most 20 values")
        values = [_normalize_tag(value) for value in values]
        accepted[key] = values
    if "llm_summary" in data:
        summary = str(data["llm_summary"]).strip()
        if len(summary) > 1000:
            raise ValueError("llm_summary is too long")
        accepted["llm_summary"] = summary
    return accepted


def _load_or_create_metadata(raw_file: Path, cache_file: Path, use_cache_only: bool, metadata_provider: MetadataProvider) -> dict[str, Any]:
    if cache_file.exists():
        logger.debug("ENRICH_CACHE_HIT raw=%s cache=%s", raw_file, cache_file)
        return json.loads(cache_file.read_text(encoding="utf-8"))
    if use_cache_only:
        logger.debug("ENRICH_CACHE_MISSING raw=%s cache=%s use_cache_only=true", raw_file, cache_file)
        raise ValueError(f"missing cached metadata: {cache_file}")
    logger.debug("ENRICH_CACHE_MISSING raw=%s cache=%s use_cache_only=false", raw_file, cache_file)
    metadata = metadata_provider.generate_metadata(raw_file.read_text(encoding="utf-8"))
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    logger.debug("ENRICH_CACHE_WRITTEN raw=%s cache=%s keys=%s", raw_file, cache_file, sorted(metadata.keys()))
    return metadata


def _copy_non_markdown_files(raw_root: Path, enriched_root: Path, ignore_dirs: list[str]) -> int:
    ignored = set(ignore_dirs)
    copied = 0
    logger.debug("ENRICH_COPY_NON_MD_START raw_root=%s enriched_root=%s", raw_root, enriched_root)
    for source in raw_root.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(raw_root)
        if set(rel.parts) & ignored or source.suffix.lower() == ".md":
            continue
        target = enriched_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
        logger.debug("ENRICH_COPY_NON_MD rel=%s target=%s", rel.as_posix(), target)
    logger.debug("ENRICH_COPY_NON_MD_DONE copied=%s", copied)
    return copied


def _as_string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("metadata value must be a list")
    result = [str(item).strip() for item in value if str(item).strip()]
    return _merge_unique([], result)


def _normalize_tag(value: str) -> str:
    tag = value.strip().replace("#", "").replace(" ", "-").lower()
    tag = re.sub(r"-{2,}", "-", tag).strip("-")
    if not tag:
        raise ValueError("tag must not be empty after normalization")
    if tag.startswith("/") or "\\" in tag or ".." in tag.split("/"):
        raise ValueError(f"tag must not be a path: {value}")
    if "/" in tag and Path(tag).suffix:
        raise ValueError(f"tag must not look like a file path: {value}")
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError(f"tag is not allowed by taxonomy: {value}")
    return tag


def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in [*existing, *incoming]:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
