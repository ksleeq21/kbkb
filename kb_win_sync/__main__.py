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
from .templates import render_windows_config_template
from .text import safe_text


def _ensure_windows_directories(config) -> list[Path]:
    directories = {
        Path(config.vault_path),
        Path(config.state_path).parent,
        Path(config.log_path).parent,
    }
    if config.sync.manifest_path is not None:
        directories.add(Path(config.sync.manifest_path).parent)
    if config.sync.key_path:
        directories.add(Path(config.sync.key_path).parent)
    ensured = sorted(directories)
    for directory in ensured:
        directory.mkdir(parents=True, exist_ok=True)
    return ensured


def _configure_logging(log_path: Path, *, verbose: bool) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    for handler in root.handlers:
        handler.close()
    root.handlers.clear()
    root.setLevel(level)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", errors="backslashreplace")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def _safe_text(value: object, *, limit: int = 500) -> str:
    return safe_text(value, limit=limit)


def _failed_email_context(folder_name: str, folder_index: int, total_label: str, email: object | None, key: str = "", target: str = "") -> str:
    return (
        f"folder={_safe_text(folder_name)} "
        f"message_index={folder_index}/{total_label} "
        f"key={_safe_text(key or '(unknown)')} "
        f"subject={_safe_text(getattr(email, 'subject', '(unavailable)') if email is not None else '(unavailable)')!r} "
        f"sender={_safe_text(getattr(email, 'sender', '(unavailable)') if email is not None else '(unavailable)')!r} "
        f"received={_safe_text(getattr(email, 'received', '(unavailable)') if email is not None else '(unavailable)')!r} "
        f"target={_safe_text(target or '(unknown)')}"
    )


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
    config_text = render_windows_config_template()
    output.write_text(config_text, encoding="utf-8")
    config = load_config(output)
    ensured = _ensure_windows_directories(config)
    print(f"created config: {output}")
    print("ensured directories:")
    for directory in ensured:
        print(f"  {directory}")
    print("next:")
    print(f"  1. kb-win-sync list-mailboxes --config {output}")
    print(f"  2. kb-win-sync doctor --config {output}")
    print(f"  3. kb-win-sync --config {output} --dry-run")
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


def _folder_config_snippet(path: str) -> str:
    slug = _slug_from_path(path)
    escaped_path = path.replace("\\", "\\\\")
    return "\n".join(
        [
            f'    - name: "{slug}"',
            f'      outlook_path: "{escaped_path}"',
            f'      target_folder: "20_Emails/{slug}"',
            "      tags:",
            '        - "email"',
            f'        - "mailbox/{slug}"',
            "      save_msg: false",
            "      save_attachments: false",
        ]
    )


def _print_folder_config_snippets(paths: list[str]) -> None:
    if not paths:
        print("No mailbox selected.")
        return
    print("")
    print("Add entries like these under outlook.folders:")
    for path in paths:
        print(_folder_config_snippet(path))


def _remove_default_placeholder_folder(config_text: str) -> str:
    lines = config_text.splitlines()
    index = next((i for i, line in enumerate(lines) if "Mailbox - User Name" in line and "outlook_path:" in line), None)
    if index is None:
        return config_text
    start = index
    while start > 0 and not lines[start].startswith("    - "):
        start -= 1
    end = index + 1
    while end < len(lines):
        line = lines[end]
        if line.startswith("    - ") or (line and not line.startswith(" ")):
            break
        end += 1
    del lines[start:end]
    return "\n".join(lines) + ("\n" if config_text.endswith("\n") else "")


def _append_folder_config_snippets(config_path: str, paths: list[str]) -> int:
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: config not found: {path}", file=sys.stderr)
        return 2
    config_text = _remove_default_placeholder_folder(path.read_text(encoding="utf-8"))
    snippets: list[str] = []
    for selected_path in paths:
        escaped_path = selected_path.replace("\\", "\\\\")
        if f'outlook_path: "{escaped_path}"' in config_text:
            print(f"skip existing outlook_path: {selected_path}")
            continue
        snippets.append(_folder_config_snippet(selected_path))
    if not snippets:
        print(f"config unchanged: {path}")
        return 0

    lines = config_text.splitlines()
    folders_index = next((i for i, line in enumerate(lines) if line.strip() == "folders:"), None)
    if folders_index is None:
        print(f"ERROR: config has no outlook.folders section: {path}", file=sys.stderr)
        return 2

    insert_at = folders_index + 1
    while insert_at < len(lines):
        line = lines[insert_at]
        if line and not line.startswith(" "):
            break
        insert_at += 1
    insert_lines = "\n".join(snippets).splitlines()
    if insert_at > 0 and insert_at <= len(lines) and lines[insert_at - 1].strip():
        insert_lines = ["", *insert_lines]
    lines[insert_at:insert_at] = insert_lines
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated config: {path}")
    print(f"added outlook.folders entries={len(snippets)}")
    print(f"next: kb-win-sync doctor --config {path}")
    return 0


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
                logging.warning("Attachment has no save hook message_key=%s filename=%s", key, _safe_text(attachment.filename))
                saved_attachments.append(attachment)
                continue
            try:
                (vault_path / rel).parent.mkdir(parents=True, exist_ok=True)
                attachment.saver(vault_path / rel)
                saved_attachments.append(replace(attachment, saved_path=rel.as_posix()))
                attachment_count += 1
                logging.info("Saved attachment message_key=%s path=%s", key, rel.as_posix())
            except Exception as exc:
                logging.error("Attachment save failed message_key=%s filename=%s error=%s", key, _safe_text(attachment.filename), _safe_text(exc))
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
            logging.info("Saved original .msg message_key=%s path=%s", key, rel.as_posix())
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
    logging.info(
        "Starting kb-win-sync import dry_run=%s folder_filter=%s force=%s vault_path=%s state_path=%s",
        dry_run,
        folder_filter or "(all)",
        force,
        config.vault_path,
        config.state_path,
    )
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
            logging.info("Skipping folder name=%s because folder_filter=%s", folder.name, folder_filter)
            continue
        selected_folders += 1
        folder_scanned_before = summary["scanned"]
        folder_imported_before = summary["imported"]
        folder_skipped_before = summary["skipped_duplicate"]
        folder_failed_before = summary["failed"]
        try:
            folder_total = client.count_folder_items(folder)
        except AttributeError:
            folder_total = None
        total_label = str(folder_total) if folder_total is not None else "unknown"
        logging.info(
            "Scanning Outlook folder name=%s outlook_path=%s target_folder=%s total_items=%s save_msg=%s save_attachments=%s",
            folder.name,
            folder.outlook_path,
            folder.target_folder,
            total_label,
            folder.save_msg,
            folder.save_attachments,
        )
        for folder_index, email in enumerate(client.iter_folder_messages(folder), start=1):
            summary["scanned"] += 1
            path = ""
            key = ""
            try:
                path = target_path(email, folder.target_folder)
                key = message_key(email)
                logging.info(
                    "Processing message %s/%s folder=%s key=%s subject=%r target=%s",
                    folder_index,
                    total_label,
                    folder.name,
                    key,
                    _safe_text(email.subject),
                    path,
                )
                if key in state.imported and not force:
                    summary["skipped_duplicate"] += 1
                    logging.info("Skipped duplicate message key=%s subject=%r target=%s", key, _safe_text(email.subject), path)
                    if dry_run:
                        print(f"skip duplicate key={key} subject={_safe_text(email.subject)!r} target={path}")
                    continue
                if dry_run:
                    logging.info("Dry-run would import message key=%s subject=%r target=%s", key, _safe_text(email.subject), path)
                    print(
                        f"import key={key} "
                        f"sender={_safe_text(email.sender)!r} "
                        f"received={_safe_text(email.received)!r} "
                        f"subject={_safe_text(email.subject)!r} "
                        f"target={path}"
                    )
                    continue
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
                logging.info(
                    "Imported message key=%s subject=%r target=%s attachments_saved=%s msg_saved=%s",
                    key,
                    _safe_text(email.subject),
                    path,
                    attachments_saved,
                    msg_saved,
                )
            except Exception as exc:
                summary["failed"] += 1
                logging.exception(
                    "FAILED_EMAIL action=skip error_type=%s error=%s %s",
                    type(exc).__name__,
                    _safe_text(exc),
                    _failed_email_context(folder.name, folder_index, total_label, email, key, path),
                )
        logging.info(
            "Folder complete name=%s scanned=%s imported=%s skipped_duplicate=%s failed=%s",
            folder.name,
            summary["scanned"] - folder_scanned_before,
            summary["imported"] - folder_imported_before,
            summary["skipped_duplicate"] - folder_skipped_before,
            summary["failed"] - folder_failed_before,
        )
    print(f"folders selected={selected_folders} excluded={excluded_folders}")
    print("summary " + " ".join(f"{key}={value}" for key, value in summary.items()))
    logging.info(
        "Import summary selected_folders=%s excluded_folders=%s %s",
        selected_folders,
        excluded_folders,
        " ".join(f"{key}={value}" for key, value in summary.items()),
    )
    if dry_run:
        print(f"next: kb-win-sync --config {config_path}")
    else:
        print("next: run enrichment/reindex on Linux after raw Markdown sync completes")
        store.save(state)
        logging.info("Saved import state path=%s imported_count=%s", config.state_path, len(state.imported))
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
        if args.config:
            return _append_folder_config_snippets(args.config, selected_paths)
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

    if not config.folders and not args.sync_only:
        print(f"ERROR: no Outlook folders configured. Run: kb-win-sync list-mailboxes --config {args.config}", file=sys.stderr)
        return 2

    _configure_logging(config.log_path, verbose=args.verbose)
    logging.info("Using config=%s log_path=%s", args.config, config.log_path)

    if not args.sync_only:
        try:
            client = OutlookClient()
        except OutlookUnavailable as exc:
            logging.error("Outlook unavailable: %s", exc)
            return 2
        logging.info("Outlook client initialized")
        run_import(
            config,
            client,
            dry_run=args.dry_run,
            folder_filter=args.folder,
            force=args.force,
            config_path=args.config,
        )

    if not args.import_only and not args.dry_run:
        logging.info("Starting SFTP sync enabled=%s remote=%s:%s", config.sync.enabled, config.sync.host, config.sync.remote_path)
        uploaded = SftpSyncer(config.sync).sync(config.vault_path)
        logging.info("SFTP sync uploaded %s files", uploaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
