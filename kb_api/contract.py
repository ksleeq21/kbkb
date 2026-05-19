CONTRACT_VERSION = "v1"

SEARCH_RESULT_FIELDS = {
    "path",
    "title",
    "type",
    "sender",
    "received",
    "folder",
    "tags",
    "chunk_index",
    "matched_fields",
    "metadata",
    "score",
    "excerpt",
}

NOTE_FIELDS = {"path", "title", "type", "metadata", "body"}

CONTEXT_EVIDENCE_FIELDS = {
    "path",
    "title",
    "type",
    "sender",
    "received",
    "excerpt",
    "why_relevant",
}

ERROR_FIELDS = {"code", "message"}
