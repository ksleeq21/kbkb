from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kb_win_sync.simple_yaml import load_simple_yaml


@dataclass(frozen=True)
class ParsedMarkdown:
    metadata: dict[str, Any]
    body: str


def parse_markdown(text: str) -> ParsedMarkdown:
    if not text.startswith("---\n"):
        return ParsedMarkdown(metadata={}, body=text)
    end = text.find("\n---", 4)
    if end == -1:
        return ParsedMarkdown(metadata={}, body=text)
    raw = text[4:end]
    body = text[text.find("\n", end + 4) + 1 :]
    try:
        metadata = load_simple_yaml(raw)
    except ValueError:
        metadata = {"_frontmatter_error": "invalid_yaml"}
    return ParsedMarkdown(metadata=metadata, body=body)
