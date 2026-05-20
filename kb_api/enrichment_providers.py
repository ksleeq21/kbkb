from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Protocol


logger = logging.getLogger(__name__)

ALLOWED_METADATA_KEYS = {"tags", "llm_tags", "llm_summary"}
SOURCE_METADATA_KEYS = {
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


class MetadataProvider(Protocol):
    def generate_metadata(self, raw_markdown: str) -> dict[str, Any]:
        ...


def build_enrichment_prompt(raw_markdown: str) -> str:
    return (
        "Return exactly one JSON object with only these optional keys: "
        "tags, llm_tags, llm_summary. Do not include source metadata such as "
        "type, source, subject, from, to, dates, source_id, message_id, conversation_id, attachments, or folder. "
        "Use evidence from this raw Markdown only.\n\n"
        + raw_markdown
    )


class ClineCliMetadataProvider:
    def __init__(self, command: str = "cline", timeout_seconds: int = 120):
        self.command = command
        self.timeout_seconds = timeout_seconds

    def generate_metadata(self, raw_markdown: str) -> dict[str, Any]:
        prompt = build_enrichment_prompt(raw_markdown)
        args = self.command.split() + ["--json", prompt]
        logger.debug("ENRICH_CLINE_START command=%s prompt_chars=%s", self.command, len(prompt))
        completed = subprocess.run(args, text=True, capture_output=True, timeout=self.timeout_seconds, check=False)
        if completed.returncode != 0:
            logger.debug("ENRICH_CLINE_FAILED returncode=%s stderr_chars=%s", completed.returncode, len(completed.stderr or ""))
            raise RuntimeError(completed.stderr.strip() or "cline command failed")
        logger.debug("ENRICH_CLINE_DONE stdout_chars=%s stderr_chars=%s", len(completed.stdout or ""), len(completed.stderr or ""))
        return parse_metadata_json(completed.stdout)


def parse_metadata_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    logger.debug("ENRICH_PARSE_START chars=%s lines=%s", len(stripped), len(stripped.splitlines()))
    try:
        parsed = json.loads(stripped)
        logger.debug("ENRICH_PARSE_WHOLE_JSON type=%s", type(parsed).__name__)
        result = _metadata_from_parsed_json(parsed)
        if result is not None:
            logger.debug("ENRICH_PARSE_WHOLE_JSON_OK keys=%s", sorted(result.keys()))
            return result
    except json.JSONDecodeError as exc:
        logger.debug("ENRICH_PARSE_WHOLE_JSON_FAILED error=%s", exc)

    messages: list[dict[str, Any]] = []
    for line in reversed(stripped.splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            messages.extend(item for item in parsed if isinstance(item, dict))
            logger.debug("ENRICH_PARSE_LINE_JSON_LIST count=%s", len(parsed))
            continue
        if isinstance(parsed, dict):
            messages.append(parsed)
            logger.debug(
                "ENRICH_PARSE_LINE_JSON_DICT type=%s say=%s keys=%s",
                parsed.get("type", ""),
                parsed.get("say", ""),
                sorted(parsed.keys()),
            )
            result = _metadata_from_direct_dict(parsed)
            if result is not None:
                logger.debug("ENRICH_PARSE_LINE_DIRECT_OK keys=%s", sorted(result.keys()))
                return result
    result = _metadata_from_cline_messages(messages)
    if result is not None:
        logger.debug("ENRICH_PARSE_MESSAGES_OK keys=%s", sorted(result.keys()))
        return result
    raise json.JSONDecodeError("No JSON object found in metadata provider output", text, 0)


def _metadata_from_parsed_json(parsed: Any) -> dict[str, Any] | None:
    if isinstance(parsed, dict):
        if isinstance(parsed.get("messages"), list):
            logger.debug("ENRICH_PARSE_WRAPPER_MESSAGES count=%s", len(parsed["messages"]))
            return _metadata_from_cline_messages([item for item in parsed["messages"] if isinstance(item, dict)])
        return _metadata_from_direct_dict(parsed)
    if isinstance(parsed, list):
        logger.debug("ENRICH_PARSE_ARRAY_MESSAGES count=%s", len(parsed))
        return _metadata_from_cline_messages([item for item in parsed if isinstance(item, dict)])
    return None


def _metadata_from_direct_dict(parsed: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(parsed.get("metadata"), dict):
        return parsed["metadata"]
    if isinstance(parsed.get("result"), dict):
        return parsed["result"]
    if set(parsed).issubset(ALLOWED_METADATA_KEYS | SOURCE_METADATA_KEYS):
        return parsed
    return None


def _metadata_from_cline_messages(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    logger.debug("ENRICH_PARSE_MESSAGES_SCAN count=%s", len(messages))
    for message in reversed(messages):
        if message.get("type") == "say" and message.get("say") == "completion_result":
            text = str(message.get("text", "") or "")
            logger.debug("ENRICH_PARSE_COMPLETION_RESULT_FOUND text_chars=%s", len(text))
            return _parse_json_text_payload(text)
    logger.debug("ENRICH_PARSE_COMPLETION_RESULT_MISSING")
    return None


def _parse_json_text_payload(text: str) -> dict[str, Any]:
    payload = _strip_json_fence(text.strip())
    logger.debug("ENRICH_PARSE_TEXT_PAYLOAD chars=%s", len(payload))
    try:
        parsed = json.loads(payload)
        logger.debug("ENRICH_PARSE_TEXT_JSON_OK type=%s", type(parsed).__name__)
        result = _metadata_from_parsed_json(parsed)
        if result is not None:
            return result
    except json.JSONDecodeError as exc:
        logger.debug("ENRICH_PARSE_TEXT_JSON_FAILED error=%s", exc)
    extracted = _extract_first_json_object(payload)
    if extracted is None:
        logger.debug("ENRICH_PARSE_TEXT_EXTRACT_FAILED")
        raise json.JSONDecodeError("No JSON object found in completion_result text", text, 0)
    logger.debug("ENRICH_PARSE_TEXT_EXTRACTED chars=%s", len(extracted))
    parsed = json.loads(extracted)
    result = _metadata_from_parsed_json(parsed)
    if result is None:
        raise json.JSONDecodeError("completion_result text did not contain metadata JSON object", text, 0)
    return result


def _strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    stripped = "\n".join(lines).strip()
    logger.debug("ENRICH_PARSE_FENCE_STRIPPED before_chars=%s after_chars=%s", len(text), len(stripped))
    return stripped


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
