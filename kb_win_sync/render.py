from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .email_model import EmailMessage
from .simple_yaml import dump_frontmatter

UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = UNSAFE_FILENAME.sub("_", value).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def message_key(email: EmailMessage) -> str:
    basis = email.message_id.strip() or "|".join(
        [email.conversation_id, email.received, email.sender, email.subject]
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
    attachments = [att.saved_path for att in email.attachments if att.saved_path]
    frontmatter = {
        "type": "email",
        "source": "outlook",
        "folder": email.folder,
        "subject": email.subject,
        "from": email.sender,
        "to": email.to,
        "cc": email.cc,
        "received": email.received,
        "conversation_id": email.conversation_id,
        "message_id": email.message_id,
        "message_key": key,
        "imported_at": imported_at or datetime.now(timezone.utc).isoformat(),
        "attachments": attachments,
        "original_msg": email.original_msg,
        "tags": email.tags,
    }
    lines = [
        dump_frontmatter(frontmatter),
        "",
        f"# {email.subject or '(no subject)'}",
        "",
        "## Metadata",
        "",
        f"- From: {email.sender}",
        f"- To: {', '.join(email.to)}",
        f"- Cc: {', '.join(email.cc)}",
        f"- Received: {email.received}",
        f"- Outlook folder: {email.folder}",
        "",
        "## Body",
        "",
        cleanup_body(email.body),
        "",
        "## Attachments",
        "",
    ]
    links = attachments + ([email.original_msg] if email.original_msg else [])
    if links:
        lines.extend(f"- [[{path}]]" for path in links)
    else:
        lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def cleanup_body(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()
