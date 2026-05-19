from __future__ import annotations

from typing import Any

from .config import ApiConfig
from .contract import CONTRACT_VERSION
from .indexer import KbApiError, index_status, read_by_path, reindex, search


def create_app(config: ApiConfig) -> Any:
    """Create a FastAPI app when the optional api dependency is installed."""
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install optional dependencies with: pip install -e '.[api]'") from exc
    import os

    app = FastAPI(title="Obsidian KB API", version="0.1.0")

    def require_token(authorization: str = Header(default="")) -> None:
        expected = os.environ.get(config.token_env, "")
        if not expected or authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="unauthorized")

    def require_admin_token(authorization: str = Header(default="")) -> None:
        expected = os.environ.get(config.admin_token_env, "")
        if not expected or authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health(deep: bool = False) -> dict[str, Any]:
        if not deep:
            return {"status": "ok", "contract_version": CONTRACT_VERSION}
        status = index_status(config)
        return {
            "status": "ok",
            "contract_version": CONTRACT_VERSION,
            "database_exists": status.database_exists,
            "notes": status.notes,
            "chunks": status.chunks,
            "newest_received": status.newest_received,
        }

    @app.get("/search", dependencies=[Depends(require_token)])
    def api_search(q: str, limit: int = 10, type: str = "", sender: str = "", folder: str = "") -> dict[str, Any]:
        filters = {k: v for k, v in {"type": type, "sender": sender, "folder": folder}.items() if v}
        try:
            return {"results": search(config, q, limit, filters)}
        except KbApiError as exc:
            raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message, "hint": exc.hint}) from exc

    @app.get("/notes/by-path", dependencies=[Depends(require_token)])
    def api_read(path: str) -> dict[str, Any]:
        try:
            return read_by_path(config, path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc

    @app.post("/context", dependencies=[Depends(require_token)])
    def api_context(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            results = search(config, str(payload.get("query", "")), int(payload.get("limit", 5)), payload.get("filters") or {})
        except KbApiError as exc:
            raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message, "hint": exc.hint}) from exc
        return {
            "evidence": [
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
        }

    @app.post("/admin/reindex", dependencies=[Depends(require_admin_token)])
    def api_reindex() -> dict[str, Any]:
        stats = reindex(config)
        return {"status": "ok", "notes": stats.notes, "chunks": stats.chunks}

    return app
