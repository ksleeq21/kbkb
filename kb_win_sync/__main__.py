from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .diagnostics import status_lines, validate_config
from .outlook import OutlookClient, OutlookUnavailable
from .render import message_key, render_markdown, target_path
from .state import StateStore
from .sync import SftpSyncer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_win_sync")
    parser.add_argument("command", nargs="?", choices=["import", "validate-config", "status"], default="import")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--folder")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--sync-only", action="store_true")
    args = parser.parse_args(argv)

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
