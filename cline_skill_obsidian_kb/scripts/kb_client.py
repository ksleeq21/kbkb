from __future__ import annotations

import json
from urllib.error import HTTPError


def format_http_error(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        error = payload.get("error", {})
        if isinstance(error, dict):
            code = error.get("code", "unknown")
            message = error.get("message", "")
            hint = error.get("hint", "")
            suffix = f" Hint: {hint}" if hint else ""
            return f"API error {exc.code}: {code} - {message}{suffix}"
    except Exception:
        pass
    return f"API error {exc.code}: {exc.reason}"
