#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import argparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kb_client import format_http_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--limit", type=int, default=int(os.environ.get("KB_API_LIMIT", "5")))
    parser.add_argument("--type", dest="note_type", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--sender", default="")
    parser.add_argument("--folder", default="")
    parser.add_argument("--after", default="")
    parser.add_argument("--before", default="")
    args = parser.parse_args()
    if not args.question.strip():
        print("question must not be empty", file=sys.stderr)
        return 2
    base = os.environ.get("KB_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    token = os.environ.get("KB_API_TOKEN", "")
    if not token:
        print("KB_API_TOKEN is not set", file=sys.stderr)
        return 2
    filters = {
        key: value
        for key, value in {
            "type": args.note_type,
            "tag": args.tag,
            "sender": args.sender,
            "folder": args.folder,
            "after": args.after,
            "before": args.before,
        }.items()
        if value
    }
    payload = json.dumps({"query": args.question, "limit": args.limit, "filters": filters}).encode()
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
        print(format_http_error(exc), file=sys.stderr)
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


if __name__ == "__main__":
    raise SystemExit(main())
