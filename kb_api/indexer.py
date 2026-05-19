from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ApiConfig
from .frontmatter import parse_markdown
from .scanner import scan_markdown


@dataclass(frozen=True)
class ReindexStats:
    notes: int
    chunks: int


class KbApiError(RuntimeError):
    code = "kb_api_error"
    status = 400

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint


class DatabaseNotIndexedError(KbApiError):
    code = "database_not_indexed"
    status = 503


class InvalidQueryError(KbApiError):
    code = "invalid_query"
    status = 400


@dataclass(frozen=True)
class IndexStatus:
    database_exists: bool
    notes: int = 0
    chunks: int = 0
    newest_received: str = ""
    fts_tokenizer: str = ""


SCHEMA_TEMPLATE = """
DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS notes;
DROP TABLE IF EXISTS index_meta;
CREATE TABLE index_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  sender TEXT,
  received TEXT,
  folder TEXT,
  tags_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  body TEXT NOT NULL,
  indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY(note_id) REFERENCES notes(id)
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, note_id UNINDEXED, chunk_id UNINDEXED{tokenizer_clause});
"""


def reindex(config: ApiConfig) -> ReindexStats:
    database_path = Path(config.database_path)
    vault_path = Path(config.vault_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    try:
        tokenizer = _create_schema(conn)
        conn.execute("INSERT INTO index_meta(key, value) VALUES ('fts_tokenizer', ?)", (tokenizer,))
        note_count = 0
        chunk_count = 0
        for path in scan_markdown(vault_path, config.ignore_dirs):
            rel = path.relative_to(vault_path).as_posix()
            parsed = parse_markdown(path.read_text(encoding="utf-8"))
            metadata = parsed.metadata
            note_id = stable_note_id(rel)
            title = str(metadata.get("subject") or first_heading(parsed.body) or Path(rel).stem)
            note_type = str(metadata.get("type") or "note")
            tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
            conn.execute(
                "INSERT INTO notes(path, id, title, type, sender, received, folder, tags_json, metadata_json, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rel,
                    note_id,
                    title,
                    note_type,
                    str(metadata.get("from") or ""),
                    str(metadata.get("received") or ""),
                    str(metadata.get("folder") or ""),
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    parsed.body,
                ),
            )
            for index, chunk in enumerate(chunk_text(parsed.body)):
                cur = conn.execute(
                    "INSERT INTO chunks(note_id, chunk_index, text) VALUES (?, ?, ?)",
                    (note_id, index, chunk),
                )
                conn.execute(
                    "INSERT INTO chunks_fts(rowid, text, note_id, chunk_id) VALUES (?, ?, ?, ?)",
                    (cur.lastrowid, chunk, note_id, cur.lastrowid),
                )
                chunk_count += 1
            note_count += 1
        conn.commit()
        return ReindexStats(notes=note_count, chunks=chunk_count)
    finally:
        conn.close()


def stable_note_id(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def chunk_text(body: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [body[:max_chars]]


def connect(config: ApiConfig) -> sqlite3.Connection:
    database_path = Path(config.database_path)
    if not database_path.exists():
        raise DatabaseNotIndexedError(
            f"Database does not exist: {database_path}",
            "Run: python3 -m kb_api reindex --config <config-path>",
        )
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def search(config: ApiConfig, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not query.strip():
        raise InvalidQueryError("Search query must not be empty", "Pass a non-empty q parameter or query field.")
    filters = filters or {}
    sql = """
    SELECT notes.*, chunks.text AS excerpt, chunks.chunk_index AS chunk_index, bm25(chunks_fts) AS score
    FROM chunks_fts
    JOIN chunks ON chunks.id = chunks_fts.chunk_id
    JOIN notes ON notes.id = chunks.note_id
    WHERE chunks_fts MATCH ?
    """
    params: list[Any] = [query]
    for key, column in {"type": "type", "sender": "sender", "folder": "folder"}.items():
        if filters.get(key):
            sql += f" AND notes.{column} = ?"
            params.append(str(filters[key]))
    tag = filters.get("tag") or filters.get("tags")
    if isinstance(tag, list):
        tag = tag[0] if tag else ""
    if tag:
        sql += " AND notes.tags_json LIKE ?"
        params.append(f'%"{str(tag)}"%')
    if filters.get("after"):
        sql += " AND notes.received >= ?"
        params.append(_date_bound(str(filters["after"]), start=True))
    if filters.get("before"):
        sql += " AND notes.received <= ?"
        params.append(_date_bound(str(filters["before"]), start=False))
    sql += " ORDER BY score LIMIT ?"
    params.append(max(1, min(int(limit), 50)))
    try:
        with connect(config) as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        raise InvalidQueryError(f"Search query is not valid for SQLite FTS: {query}", "Try simpler keywords without FTS operators.") from exc
    return [_row_to_result(row) for row in rows]


def read_by_path(config: ApiConfig, rel_path: str) -> dict[str, Any]:
    safe = safe_relative_path(rel_path)
    with connect(config) as conn:
        row = conn.execute("SELECT * FROM notes WHERE path = ?", (safe,)).fetchone()
    if row is None:
        raise FileNotFoundError(safe)
    return _row_to_note(row)


def index_status(config: ApiConfig) -> IndexStatus:
    database_path = Path(config.database_path)
    if not database_path.exists():
        return IndexStatus(database_exists=False)
    with sqlite3.connect(database_path) as conn:
        notes = int(conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0])
        chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        newest = conn.execute("SELECT MAX(received) FROM notes").fetchone()[0] or ""
        tokenizer = ""
        try:
            row = conn.execute("SELECT value FROM index_meta WHERE key = 'fts_tokenizer'").fetchone()
            tokenizer = str(row[0]) if row else ""
        except sqlite3.OperationalError:
            tokenizer = ""
    return IndexStatus(database_exists=True, notes=notes, chunks=chunks, newest_received=str(newest), fts_tokenizer=tokenizer)


def _create_schema(conn: sqlite3.Connection) -> str:
    try:
        conn.executescript(SCHEMA_TEMPLATE.format(tokenizer_clause=", tokenize = 'trigram'"))
        return "trigram"
    except sqlite3.OperationalError:
        conn.executescript(SCHEMA_TEMPLATE.format(tokenizer_clause=""))
        return "default"


def _date_bound(value: str, *, start: bool) -> str:
    stripped = value.strip()
    if len(stripped) == 10 and stripped[4] == "-" and stripped[7] == "-":
        return stripped + ("T00:00:00" if start else "T23:59:59")
    return stripped


def safe_relative_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or str(path).strip() == "":
        raise ValueError("Only vault-relative paths are allowed")
    return candidate.as_posix()


def _row_to_result(row: sqlite3.Row) -> dict[str, Any]:
    metadata = json.loads(row["metadata_json"])
    tags = json.loads(row["tags_json"])
    return {
        "path": row["path"],
        "title": row["title"],
        "type": row["type"],
        "sender": row["sender"],
        "received": row["received"],
        "folder": row["folder"],
        "tags": tags,
        "chunk_index": row["chunk_index"] if "chunk_index" in row.keys() else 0,
        "matched_fields": ["body"],
        "metadata": metadata,
        "score": row["score"],
        "excerpt": row["excerpt"][:600],
    }


def _row_to_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "path": row["path"],
        "title": row["title"],
        "type": row["type"],
        "metadata": json.loads(row["metadata_json"]),
        "body": row["body"],
    }
