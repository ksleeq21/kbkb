from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    saved_path: str = ""
    saver: Callable[[Path], None] | None = field(default=None, repr=False, compare=False)


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
    original_msg_saver: Callable[[Path], None] | None = field(default=None, repr=False, compare=False)
