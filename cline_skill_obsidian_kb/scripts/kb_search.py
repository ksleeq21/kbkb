#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=int(os.environ.get("KB_API_LIMIT", "10")))
    parser.add_argument("--type", dest="note_type", default="")
    parser.add_argument("--sender", default="")
    parser.add_argument("--folder", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.query.strip():
        print("query must not be empty", file=sys.stderr)
        return 2
    base = os.environ.get("KB_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    token = os.environ.get("KB_API_TOKEN", "")
    if not token:
        print("KB_API_TOKEN is not set", file=sys.stderr)
        return 2
    params = {"q": args.query, "limit": str(args.limit)}
    if args.note_type:
        params["type"] = args.note_type
    if args.sender:
        params["sender"] = args.sender
    if args.folder:
        params["folder"] = args.folder
    url = f"{base}/search?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=10) as response:
            data = json.load(response)
    except HTTPError as exc:
        print(_http_error(exc), file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"API connection failed: {exc.reason}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    for item in data.get("results", []):
        sender = item.get("sender") or item.get("metadata", {}).get("from", "")
        received = item.get("received") or item.get("metadata", {}).get("received", "")
        print(f"- {item['path']} | {item.get('title','')} | type={item.get('type','')} sender={sender} received={received}")
        print(f"  {item.get('excerpt','').replace(chr(10), ' ')[:300]}")
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
