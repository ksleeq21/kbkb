from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .config import OutlookFolderConfig
from .email_model import EmailAttachment, EmailMessage


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
        for item in outlook_folder.Items:
            if getattr(item, "Class", None) != 43:  # olMail
                continue
            yield EmailMessage(
                subject=str(getattr(item, "Subject", "") or ""),
                sender=str(getattr(item, "SenderEmailAddress", "") or getattr(item, "SenderName", "") or ""),
                to=[part.strip() for part in str(getattr(item, "To", "") or "").split(";") if part.strip()],
                cc=[part.strip() for part in str(getattr(item, "CC", "") or "").split(";") if part.strip()],
                received=str(getattr(item, "ReceivedTime", "") or ""),
                body=str(getattr(item, "Body", "") or ""),
                folder=folder.outlook_path,
                conversation_id=str(getattr(item, "ConversationID", "") or ""),
                message_id=_property(item, "http://schemas.microsoft.com/mapi/proptag/0x1035001E"),
                tags=folder.tags,
                attachments=[EmailAttachment(str(att.FileName)) for att in getattr(item, "Attachments", [])],
            )

    def list_mail_folders(self, max_depth: int = 6) -> list[OutlookFolderInfo]:
        folders: list[OutlookFolderInfo] = []

        def walk(com_folder, path: str, depth: int) -> None:
            if depth > max_depth:
                return
            folders.append(
                OutlookFolderInfo(
                    index=len(folders) + 1,
                    path=path,
                    name=str(getattr(com_folder, "Name", "") or path.rsplit("\\", 1)[-1]),
                    depth=depth,
                )
            )
            try:
                children = com_folder.Folders
            except Exception:
                return
            for child in children:
                name = str(getattr(child, "Name", "") or "")
                if not name:
                    continue
                walk(child, f"{path}\\{name}", depth + 1)

        for root in self._outlook.Folders:
            name = str(getattr(root, "Name", "") or "")
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
        return str(item.PropertyAccessor.GetProperty(uri) or "")
    except Exception:
        return ""
