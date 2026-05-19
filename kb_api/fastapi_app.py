from __future__ import annotations

from typing import Any

from .config import ApiConfig
from .contract import CONTRACT_VERSION
from .indexer import KbApiError, index_status, read_by_path, reindex, search


def create_app(config: ApiConfig) -> Any:
    """Create a FastAPI app when the optional api dependency is installed."""
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Request
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError("Install optional dependencies with: pip install -e '.[api]'") from exc
    import os

    app = FastAPI(title="Obsidian KB API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            error = {
                "code": str(detail.get("code", _code_for_status(exc.status_code))),
                "message": str(detail.get("message", detail.get("code", "Request failed"))),
            }
            if detail.get("hint"):
                error["hint"] = str(detail["hint"])
        else:
            error = {"code": _code_for_status(exc.status_code), "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "Request validation failed"}},
        )

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
            "fts_tokenizer": status.fts_tokenizer,
        }

    @app.get("/search", dependencies=[Depends(require_token)])
    def api_search(
        q: str,
        limit: int = 10,
        type: str = "",
        tag: str = "",
        sender: str = "",
        folder: str = "",
        after: str = "",
        before: str = "",
    ) -> dict[str, Any]:
        filters = {k: v for k, v in {"type": type, "tag": tag, "sender": sender, "folder": folder, "after": after, "before": before}.items() if v}
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


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        404: "not_found",
        503: "database_not_indexed",
    }.get(status_code, "kb_api_error")
