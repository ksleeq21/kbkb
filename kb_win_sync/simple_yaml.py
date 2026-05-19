from __future__ import annotations

from typing import Any


def load_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by the example configs."""
    lines = [line.rstrip() for line in text.splitlines()]
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    def parse_scalar(value: str) -> Any:
        value = value.strip()
        if value == "":
            return ""
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            return value

    for idx, raw in enumerate(lines):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            item_text = line[2:]
            if not isinstance(parent, list):
                raise ValueError(f"List item without list parent: {raw}")
            if ": " in item_text or item_text.endswith(":"):
                item: dict[str, Any] = {}
                parent.append(item)
                stack.append((indent, item))
                if item_text.endswith(":"):
                    item[item_text[:-1]] = {}
                else:
                    key, value = item_text.split(":", 1)
                    item[key.strip()] = parse_scalar(value)
            else:
                parent.append(parse_scalar(item_text))
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            next_container: Any = []
            for next_raw in lines[idx + 1 :]:
                if not next_raw.strip() or next_raw.lstrip().startswith("#"):
                    continue
                next_indent = len(next_raw) - len(next_raw.lstrip(" "))
                if next_indent <= indent:
                    break
                next_container = [] if next_raw.strip().startswith("- ") else {}
                break
            parent[key] = next_container
            stack.append((indent, next_container))
        else:
            parent[key] = parse_scalar(value)
    return root


def dump_frontmatter(data: dict[str, Any]) -> str:
    def scalar(value: Any) -> str:
        if value is None:
            return '""'
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value).replace('"', '\\"')
        return f'"{text}"'

    lines: list[str] = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {scalar(item)}")
        else:
            lines.append(f"{key}: {scalar(value)}")
    lines.append("---")
    return "\n".join(lines)
