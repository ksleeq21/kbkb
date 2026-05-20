from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import load_config
from .email_model import EmailAttachment, EmailMessage
from .diagnostics import doctor_lines, status_lines, validate_config
from .outlook import OutlookClient, OutlookUnavailable
from .render import message_key, render_markdown, sanitize_filename, target_path
from .state import StateStore
from .sync import SftpSyncer
from .templates import WINDOWS_CONFIG_TEMPLATE


def _write_config_template(output_arg: str | None, *, force: bool) -> int:
    if not output_arg:
        print("ERROR: --output is required for init-config", file=sys.stderr)
        return 2
    output = Path(output_arg)
    if output.exists() and not force:
        print(f"ERROR: config already exists: {output}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(WINDOWS_CONFIG_TEMPLATE, encoding="utf-8")
    print(f"created config: {output}")
    print("next:")
    print(f"  1. edit {output}")
    print("  2. kb-win-sync list-mailboxes")
    print(f"  3. kb-win-sync doctor --config {output}")
    return 0


def _print_check_result(result) -> int:
    for item in result.errors:
        print(f"ERROR: {item}")
    for item in result.warnings:
        print(f"WARNING: {item}")
    if result.ok:
        print("config: ok")
        return 0
    print("config: failed", file=sys.stderr)
    return 2


def parse_mailbox_selection(text: str, max_index: int) -> list[int]:
    selected: list[int] = []
    seen: set[int] = set()
    for raw_part in text.replace(" ", "").split(","):
        if not raw_part:
            continue
        if not raw_part.isdigit():
            raise ValueError(f"invalid mailbox index: {raw_part}")
        index = int(raw_part)
        if index < 1 or index > max_index:
            raise ValueError(f"mailbox index out of range: {index}")
        if index not in seen:
            selected.append(index)
            seen.add(index)
    return selected


def _slug_from_path(path: str) -> str:
    leaf = path.replace("/", "\\").rstrip("\\").rsplit("\\", 1)[-1]
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in leaf).strip("-")
    return slug or "mailbox"


def _print_folder_config_snippets(paths: list[str]) -> None:
    if not paths:
        print("No mailbox selected.")
        return
    print("")
    print("Add entries like these under outlook.folders:")
    for path in paths:
        slug = _slug_from_path(path)
        print("    - name: " + f'"{slug}"')
        print("      outlook_path: " + f'"{path.replace(chr(92), chr(92) + chr(92))}"')
        print("      target_folder: " + f'"20_Emails/{slug}"')
        print("      tags:")
        print('        - "email"')
        print(f'        - "mailbox/{slug}"')
        print("      save_msg: true")
        print("      save_attachments: true")


def save_email_artifacts(email: EmailMessage, vault_path: Path, *, save_msg: bool, save_attachments: bool) -> tuple[EmailMessage, int, int]:
    key = message_key(email)
    artifact_dir_rel = Path("90_Attachments") / "email" / key
    artifact_dir = vault_path / artifact_dir_rel
    saved_attachments: list[EmailAttachment] = []
    attachment_count = 0
    used_names: dict[str, int] = {}
    if save_attachments:
        for attachment in email.attachments:
            rel = artifact_dir_rel / _unique_attachment_name(attachment.filename, used_names)
            if attachment.saver is None:
                logging.warning("Attachment has no save hook message_key=%s filename=%s", key, attachment.filename)
                saved_attachments.append(attachment)
                continue
            try:
                (vault_path / rel).parent.mkdir(parents=True, exist_ok=True)
                attachment.saver(vault_path / rel)
                saved_attachments.append(replace(attachment, saved_path=rel.as_posix()))
                attachment_count += 1
            except Exception as exc:
                logging.error("Attachment save failed message_key=%s filename=%s error=%s", key, attachment.filename, exc)
                saved_attachments.append(attachment)
    else:
        saved_attachments = list(email.attachments)

    original_msg = email.original_msg
    msg_count = 0
    if save_msg and email.original_msg_saver is not None:
        rel = artifact_dir_rel / "original.msg"
        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            email.original_msg_saver(vault_path / rel)
            original_msg = rel.as_posix()
            msg_count = 1
        except Exception as exc:
            logging.error("Original .msg save failed message_key=%s error=%s", key, exc)
    elif save_msg:
        logging.warning("Original .msg has no save hook message_key=%s", key)
    return replace(email, attachments=saved_attachments, original_msg=original_msg), attachment_count, msg_count


def _unique_attachment_name(filename: str, used_names: dict[str, int]) -> str:
    safe = Path(filename).name
    safe = sanitize_filename(safe, "attachment")
    stem = Path(safe).stem
    suffix = Path(safe).suffix
    count = used_names.get(safe, 0)
    used_names[safe] = count + 1
    if count == 0:
        return safe
    return f"{stem}-{count + 1}{suffix}"


def run_import(
    config,
    client: Any,
    *,
    dry_run: bool,
    folder_filter: str | None,
    force: bool,
    config_path: str,
) -> dict[str, int]:
    store = StateStore(config.state_path)
    state = store.load()
    summary = {
        "scanned": 0,
        "imported": 0,
        "skipped_duplicate": 0,
        "failed": 0,
        "attachments_saved": 0,
        "msg_saved": 0,
    }
    selected_folders = 0
    excluded_folders = 0
    for folder in config.folders:
        if folder_filter and folder.name != folder_filter:
            excluded_folders += 1
            continue
        selected_folders += 1
        for email in client.iter_folder_messages(folder):
            summary["scanned"] += 1
            path = target_path(email, folder.target_folder)
            key = message_key(email)
            if key in state.imported and not force:
                summary["skipped_duplicate"] += 1
                if dry_run:
                    print(f"skip duplicate key={key} subject={email.subject!r} target={path}")
                continue
            if dry_run:
                print(f"import key={key} sender={email.sender!r} received={email.received!r} subject={email.subject!r} target={path}")
                continue
            try:
                email, attachments_saved, msg_saved = save_email_artifacts(
                    email,
                    config.vault_path,
                    save_msg=folder.save_msg,
                    save_attachments=folder.save_attachments,
                )
                output = config.vault_path / Path(path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(render_markdown(email, folder.target_folder), encoding="utf-8")
                state.mark_imported(key, path)
                summary["imported"] += 1
                summary["attachments_saved"] += attachments_saved
                summary["msg_saved"] += msg_saved
            except OSError as exc:
                summary["failed"] += 1
                logging.error("Import failed for message_key=%s target=%s error=%s", key, path, exc)
    print(f"folders selected={selected_folders} excluded={excluded_folders}")
    print("summary " + " ".join(f"{key}={value}" for key, value in summary.items()))
    if dry_run:
        print(f"next: kb-win-sync --config {config_path}")
    else:
        print("next: run enrichment/reindex on Linux after raw Markdown sync completes")
        store.save(state)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_win_sync")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["import", "validate-config", "status", "doctor", "init-config", "list-mailboxes"],
        default="import",
    )
    parser.add_argument("--config")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--folder")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--sync-only", action="store_true")
    parser.add_argument("--max-depth", type=int, default=6)
    args = parser.parse_args(argv)

    if args.command == "init-config":
        return _write_config_template(args.output, force=args.force)
    if args.command == "list-mailboxes":
        try:
            client = OutlookClient()
        except OutlookUnavailable as exc:
            print(f"ERROR: Outlook unavailable: {exc}", file=sys.stderr)
            return 2
        folders = client.list_mail_folders(max_depth=args.max_depth)
        if not folders:
            print("No Outlook mailboxes or folders found.")
            return 0
        for folder in folders:
            indent = "  " * max(folder.depth - 1, 0)
            print(f"{folder.index}. {indent}{folder.path}")
        try:
            answer = input("동기화 시키고 싶은 메일함 Index(예: 1,2,3,5): ")
            selected = parse_mailbox_selection(answer, len(folders))
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        selected_paths = [folders[index - 1].path for index in selected]
        _print_folder_config_snippets(selected_paths)
        return 0
    if not args.config:
        print(f"ERROR: --config is required for {args.command}", file=sys.stderr)
        return 2
    config = load_config(args.config)
    if args.command == "validate-config":
        return _print_check_result(validate_config(config))
    if args.command == "status":
        print("\n".join(status_lines(config)))
        return 0
    if args.command == "doctor":
        lines, ok = doctor_lines(config)
        print("\n".join(lines))
        return 0 if ok else 2

    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=config.log_path,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.sync_only:
        try:
            client = OutlookClient()
        except OutlookUnavailable as exc:
            logging.error("Outlook unavailable: %s", exc)
            return 2
        run_import(
            config,
            client,
            dry_run=args.dry_run,
            folder_filter=args.folder,
            force=args.force,
            config_path=args.config,
        )

    if not args.import_only and not args.dry_run:
        uploaded = SftpSyncer(config.sync).sync(config.vault_path)
        logging.info("SFTP sync uploaded %s files", uploaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
