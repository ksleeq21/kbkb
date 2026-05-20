from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from .config import OutlookFolderConfig
from .email_model import EmailAttachment, EmailMessage
from .text import normalize_text, safe_text


class OutlookUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OutlookFolderInfo:
    index: int
    path: str
    name: str
    depth: int


class OutlookClient:
    def __init__(self) -> None:
        try:
            import win32com.client  # type: ignore
        except ImportError as exc:
            raise OutlookUnavailable("pywin32 is required on Windows for Outlook import") from exc
        self._win32 = win32com.client
        self._outlook = self._win32.Dispatch("Outlook.Application").GetNamespace("MAPI")

    def iter_folder_messages(self, folder: OutlookFolderConfig) -> Iterable[EmailMessage]:
        outlook_folder = self._resolve_folder(folder.outlook_path)
        for index, item in enumerate(outlook_folder.Items, start=1):
            try:
                if getattr(item, "Class", None) != 43:  # olMail
                    continue
                yield EmailMessage(
                    subject=normalize_text(getattr(item, "Subject", "") or ""),
                    sender=normalize_text(getattr(item, "SenderEmailAddress", "") or getattr(item, "SenderName", "") or ""),
                    to=[normalize_text(part.strip()) for part in str(getattr(item, "To", "") or "").split(";") if part.strip()],
                    cc=[normalize_text(part.strip()) for part in str(getattr(item, "CC", "") or "").split(";") if part.strip()],
                    received=normalize_text(getattr(item, "ReceivedTime", "") or ""),
                    body=normalize_text(getattr(item, "Body", "") or ""),
                    folder=normalize_text(folder.outlook_path),
                    conversation_id=normalize_text(getattr(item, "ConversationID", "") or ""),
                    message_id=_property(item, "http://schemas.microsoft.com/mapi/proptag/0x1035001E"),
                    tags=[normalize_text(tag) for tag in folder.tags],
                    attachments=[EmailAttachment(normalize_text(att.FileName), saver=_attachment_saver(att)) for att in getattr(item, "Attachments", [])],
                    original_msg_saver=_message_saver(item),
                )
            except Exception as exc:
                logging.exception(
                    "FAILED_EMAIL action=skip stage=outlook_read folder=%s message_index=%s error_type=%s error=%s",
                    safe_text(folder.name),
                    index,
                    type(exc).__name__,
                    safe_text(exc),
                )
                continue

    def count_folder_items(self, folder: OutlookFolderConfig) -> int | None:
        outlook_folder = self._resolve_folder(folder.outlook_path)
        try:
            return int(getattr(outlook_folder.Items, "Count"))
        except Exception:
            return None

    def list_mail_folders(self, max_depth: int = 6) -> list[OutlookFolderInfo]:
        folders: list[OutlookFolderInfo] = []

        def walk(com_folder, path: str, depth: int) -> None:
            if depth > max_depth:
                return
            folders.append(
                OutlookFolderInfo(
                    index=len(folders) + 1,
                    path=path,
                    name=normalize_text(getattr(com_folder, "Name", "") or path.rsplit("\\", 1)[-1]),
                    depth=depth,
                )
            )
            try:
                children = com_folder.Folders
            except Exception:
                return
            for child in children:
                name = normalize_text(getattr(child, "Name", "") or "")
                if not name:
                    continue
                walk(child, f"{path}\\{name}", depth + 1)

        for root in self._outlook.Folders:
            name = normalize_text(getattr(root, "Name", "") or "")
            if not name:
                continue
            walk(root, f"\\{name}", 1)
        return folders

    def _resolve_folder(self, path: str):
        parts = [part for part in path.replace("/", "\\").split("\\") if part]
        if not parts:
            raise ValueError("Outlook folder path is empty")
        folder = self._outlook.Folders.Item(parts[0])
        for part in parts[1:]:
            folder = folder.Folders.Item(part)
        return folder


def _property(item, uri: str) -> str:
    try:
        return normalize_text(item.PropertyAccessor.GetProperty(uri) or "")
    except Exception:
        return ""


def _attachment_saver(attachment):
    def save(path) -> None:
        attachment.SaveAsFile(str(path))

    return save


def _message_saver(item):
    def save(path) -> None:
        item.SaveAs(str(path), 3)  # olMSG

    return save
