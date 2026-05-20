from __future__ import annotations


def safe_text(value: object, *, limit: int | None = None) -> str:
    text = normalize_text(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if limit is not None and len(text) > limit:
        return text[:limit] + "...(truncated)"
    return text


def normalize_text(value: object) -> str:
    return str(value).encode("utf-8", errors="backslashreplace").decode("utf-8", errors="replace")


def normalize_text_list(values: list[str]) -> list[str]:
    return [normalize_text(value) for value in values]
