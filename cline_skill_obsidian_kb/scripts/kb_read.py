#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("usage: kb_read.py <vault-relative-path>", file=sys.stderr)
        return 2
    base = os.environ.get("KB_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    token = os.environ.get("KB_API_TOKEN", "")
    if not token:
        print("KB_API_TOKEN is not set", file=sys.stderr)
        return 2
    req = Request(f"{base}/notes/by-path?{urlencode({'path': sys.argv[1]})}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=10) as response:
            data = json.load(response)
    except HTTPError as exc:
        print(_http_error(exc), file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"API connection failed: {exc.reason}", file=sys.stderr)
        return 1
    print(f"# {data.get('title', '')}")
    print(f"source: {data.get('path', '')}")
    print(json.dumps(data.get("metadata", {}), ensure_ascii=False, indent=2))
    print(data.get("body", ""))
    return 0


def _http_error(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        error = payload.get("error", {})
        if isinstance(error, dict):
            return f"API error {exc.code}: {error.get('code', 'unknown')} - {error.get('message', '')}"
    except Exception:
        pass
    return f"API error {exc.code}: {exc.reason}"


if __name__ == "__main__":
    raise SystemExit(main())
