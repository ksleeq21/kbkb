from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import ApiConfig
from .contract import CONTRACT_VERSION
from .indexer import KbApiError, index_status, read_by_path, reindex, search


def serve(config: ApiConfig) -> None:
    class Handler(KbHandler):
        api_config = config

    server = ThreadingHTTPServer((config.host, config.port), Handler)
    server.serve_forever()


class KbHandler(BaseHTTPRequestHandler):
    api_config: ApiConfig

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/health":
            if qs.get("deep", ["false"])[0].lower() == "true":
                status = index_status(self.api_config)
                self._json(
                    200,
                    {
                        "status": "ok",
                        "contract_version": CONTRACT_VERSION,
                        "database_exists": status.database_exists,
                        "notes": status.notes,
                        "chunks": status.chunks,
                        "newest_received": status.newest_received,
                        "fts_tokenizer": status.fts_tokenizer,
                    },
                )
            else:
                self._json(200, {"status": "ok", "contract_version": CONTRACT_VERSION})
            return
        if not self._authorized(os.environ.get(self.api_config.token_env, "")):
            self._json(401, {"error": {"code": "unauthorized", "message": "Missing or invalid bearer token"}})
            return
        try:
            if parsed.path == "/search":
                results = search(
                    self.api_config,
                    qs.get("q", [""])[0],
                    int(qs.get("limit", ["10"])[0]),
                    {k: v[0] for k, v in qs.items() if k in {"type", "tag", "sender", "folder", "after", "before"}},
                )
                self._json(200, {"results": results})
                return
            if parsed.path == "/notes/by-path":
                self._json(200, read_by_path(self.api_config, qs.get("path", [""])[0]))
                return
        except ValueError as exc:
            self._json(400, {"error": {"code": "bad_request", "message": str(exc)}})
            return
        except KbApiError as exc:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message, "hint": exc.hint}})
            return
        except FileNotFoundError:
            self._json(404, {"error": {"code": "not_found", "message": "Note path was not found in the index"}})
            return
        self._json(404, {"error": {"code": "not_found", "message": "Endpoint not found"}})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        token_env = self.api_config.admin_token_env if parsed.path.startswith("/admin/") else self.api_config.token_env
        if not self._authorized(os.environ.get(token_env, "")):
            self._json(401, {"error": {"code": "unauthorized", "message": "Missing or invalid bearer token"}})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": {"code": "bad_request", "message": "Request body must be valid JSON"}})
            return
        try:
            if parsed.path == "/context":
                results = search(self.api_config, str(body.get("query", "")), int(body.get("limit", 5)), body.get("filters") or {})
            else:
                results = []
        except ValueError as exc:
            self._json(400, {"error": {"code": "bad_request", "message": str(exc)}})
            return
        except KbApiError as exc:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message, "hint": exc.hint}})
            return
        if parsed.path == "/context":
            evidence = [
                {
                    "path": item["path"],
                    "title": item["title"],
                    "type": item["type"],
                    "received": item["metadata"].get("received", ""),
                    "sender": item["metadata"].get("from", ""),
                    "excerpt": item["excerpt"][:500],
                    "why_relevant": "Matched the context query through the local SQLite FTS index.",
                }
                for item in results
            ]
            self._json(200, {"evidence": evidence})
            return
        if parsed.path == "/admin/reindex":
            stats = reindex(self.api_config)
            self._json(200, {"status": "ok", "notes": stats.notes, "chunks": stats.chunks})
            return
        self._json(404, {"error": {"code": "not_found", "message": "Endpoint not found"}})

    def log_message(self, fmt: str, *args) -> None:
        return

    def _authorized(self, expected: str) -> bool:
        header = self.headers.get("Authorization", "")
        return bool(expected) and header == f"Bearer {expected}"

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
