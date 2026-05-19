#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: kb_context.py <question>", file=sys.stderr)
        return 2
    base = os.environ.get("KB_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    token = os.environ.get("KB_API_TOKEN", "")
    if not token:
        print("KB_API_TOKEN is not set", file=sys.stderr)
        return 2
    payload = json.dumps({"query": sys.argv[1], "limit": int(os.environ.get("KB_API_LIMIT", "5"))}).encode()
    req = Request(
        f"{base}/context",
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=10) as response:
            data = json.load(response)
    except HTTPError as exc:
        print(_http_error(exc), file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"API connection failed: {exc.reason}", file=sys.stderr)
        return 1
    for idx, item in enumerate(data.get("evidence", []), start=1):
        print(f"Evidence {idx}")
        print(f"source: {item['path']}")
        print(f"title: {item.get('title','')}")
        print(f"type: {item.get('type','')}")
        print(f"sender: {item.get('sender','')}")
        print(f"received: {item.get('received','')}")
        print(f"why: {item.get('why_relevant','')}")
        print(f"excerpt: {item.get('excerpt','').replace(chr(10), ' ')[:500]}")
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
