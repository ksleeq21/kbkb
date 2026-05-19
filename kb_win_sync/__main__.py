from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .diagnostics import doctor_lines, status_lines, validate_config
from .outlook import OutlookClient, OutlookUnavailable
from .render import message_key, render_markdown, target_path
from .state import StateStore
from .sync import SftpSyncer
from .templates import WINDOWS_CONFIG_TEMPLATE


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
        if not args.output:
            print("ERROR: --output is required for init-config", file=sys.stderr)
            return 2
        output = Path(args.output)
        if output.exists() and not args.force:
            print(f"ERROR: config already exists: {output}", file=sys.stderr)
            print("Use --force to overwrite.", file=sys.stderr)
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(WINDOWS_CONFIG_TEMPLATE, encoding="utf-8")
        print(f"created config: {output}")
        print(f"next: edit {output}")
        print(f"next: python -m kb_win_sync validate-config --config {output}")
        return 0
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
        result = validate_config(config)
        for item in result.errors:
            print(f"ERROR: {item}")
        for item in result.warnings:
            print(f"WARNING: {item}")
        if result.ok:
            print("config: ok")
            return 0
        print("config: failed", file=sys.stderr)
        return 2
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
            if args.folder and folder.name != args.folder:
                excluded_folders += 1
                continue
            selected_folders += 1
            for email in client.iter_folder_messages(folder):
                summary["scanned"] += 1
                path = target_path(email, folder.target_folder)
                key = message_key(email)
                if key in state.imported and not args.force:
                    summary["skipped_duplicate"] += 1
                    if args.dry_run:
                        print(f"skip duplicate key={key} subject={email.subject!r} target={path}")
                    continue
                if args.dry_run:
                    print(f"import key={key} sender={email.sender!r} received={email.received!r} subject={email.subject!r} target={path}")
                    continue
                try:
                    output = config.vault_path / Path(path)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(render_markdown(email, folder.target_folder), encoding="utf-8")
                    state.mark_imported(key, path)
                    summary["imported"] += 1
                except OSError as exc:
                    summary["failed"] += 1
                    logging.error("Import failed for message_key=%s target=%s error=%s", key, path, exc)
        print(f"folders selected={selected_folders} excluded={excluded_folders}")
        print("summary " + " ".join(f"{key}={value}" for key, value in summary.items()))
        if not args.dry_run:
            store.save(state)

    if not args.import_only and not args.dry_run:
        uploaded = SftpSyncer(config.sync).sync(config.vault_path)
        logging.info("SFTP sync uploaded %s files", uploaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
