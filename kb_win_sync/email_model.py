from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    saved_path: str = ""


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    sender: str
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    received: str = ""
    body: str = ""
    folder: str = ""
    conversation_id: str = ""
    message_id: str = ""
    tags: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)
    original_msg: str = ""
