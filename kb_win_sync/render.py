from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .email_model import EmailMessage
from .simple_yaml import dump_frontmatter
from .text import normalize_text, normalize_text_list

UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = UNSAFE_FILENAME.sub("_", normalize_text(value)).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def message_key(email: EmailMessage) -> str:
    basis = normalize_text(email.message_id).strip() or "|".join(
        [
            normalize_text(email.conversation_id),
            normalize_text(email.received),
            normalize_text(email.sender),
            normalize_text(email.subject),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


def target_path(email: EmailMessage, target_folder: str) -> str:
    key = message_key(email)
    try:
        dt = datetime.fromisoformat(email.received.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    subject = sanitize_filename(email.subject)
    max_subject = 80
    if len(subject) > max_subject:
        subject = subject[:max_subject].rstrip()
    filename = f"{dt:%Y-%m-%d_%H%M}__{subject}__{key}.md"
    return str(Path(target_folder) / f"{dt:%Y}" / f"{dt:%m}" / filename).replace("\\", "/")


def render_markdown(email: EmailMessage, target_folder: str, imported_at: str | None = None) -> str:
    key = message_key(email)
    attachments = [normalize_text(att.saved_path) for att in email.attachments if att.saved_path]
    subject = normalize_text(email.subject)
    sender = normalize_text(email.sender)
    to = normalize_text_list(email.to)
    cc = normalize_text_list(email.cc)
    received = normalize_text(email.received)
    folder = normalize_text(email.folder)
    frontmatter = {
        "type": "email",
        "source": "outlook",
        "folder": folder,
        "subject": subject,
        "from": sender,
        "to": to,
        "cc": cc,
        "received": received,
        "conversation_id": normalize_text(email.conversation_id),
        "message_id": normalize_text(email.message_id),
        "message_key": key,
        "imported_at": imported_at or datetime.now(timezone.utc).isoformat(),
        "attachments": attachments,
        "original_msg": normalize_text(email.original_msg),
        "tags": normalize_text_list(email.tags),
    }
    lines = [
        dump_frontmatter(frontmatter),
        "",
        f"# {subject or '(no subject)'}",
        "",
        "## Metadata",
        "",
        f"- From: {sender}",
        f"- To: {', '.join(to)}",
        f"- Cc: {', '.join(cc)}",
        f"- Received: {received}",
        f"- Outlook folder: {folder}",
        "",
        "## Body",
        "",
        cleanup_body(normalize_text(email.body)),
        "",
        "## Attachments",
        "",
    ]
    original_msg = normalize_text(email.original_msg)
    links = attachments + ([original_msg] if original_msg else [])
    if links:
        lines.extend(f"- [[{path}]]" for path in links)
    else:
        lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def cleanup_body(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()
