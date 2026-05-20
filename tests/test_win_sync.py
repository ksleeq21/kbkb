from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kb_win_sync.__main__ import _append_folder_config_snippets, _configure_logging, parse_mailbox_selection, run_import, save_email_artifacts
from kb_win_sync.config import OutlookFolderConfig, SyncConfig, WinConfig, load_config, parse_config
from kb_win_sync.email_model import EmailAttachment, EmailMessage
from kb_win_sync.render import message_key, render_markdown, sanitize_filename, target_path
from kb_win_sync.state import ImportState, StateStore
from kb_win_sync.sync import build_incremental_sync_plan, load_manifest, save_manifest


class WinSyncTests(unittest.TestCase):
    def test_windows_config_parses_example(self) -> None:
        config = load_config("examples/windows-config.example.yaml")
        self.assertEqual(config.folders[0].name, "project-a")
        self.assertFalse(config.folders[0].save_msg)
        self.assertFalse(config.folders[0].save_attachments)
        self.assertFalse(config.sync.enabled)

    def test_windows_config_defaults_do_not_save_msg_or_attachments(self) -> None:
        config = parse_config(
            {
                "vault_path": "D:/KnowledgeVault",
                "state_path": "state.json",
                "log_path": "log.txt",
                "outlook": {
                    "folders": [
                        {
                            "name": "project-a",
                            "outlook_path": "\\Mailbox\\Inbox\\_KB\\ProjectA",
                            "target_folder": "20_Emails/ProjectA",
                        }
                    ]
                },
            }
        )
        self.assertFalse(config.folders[0].save_msg)
        self.assertFalse(config.folders[0].save_attachments)

    def test_windows_config_reports_missing_folder_keys(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            parse_config(
                {
                    "vault_path": "D:/KnowledgeVault",
                    "state_path": "state.json",
                    "log_path": "log.txt",
                    "outlook": {"folders": [{"name": "bad"}]},
                }
        )
        self.assertIn("missing: outlook_path, target_folder", str(ctx.exception))

    def test_windows_config_allows_empty_initial_folder_list(self) -> None:
        config = parse_config(
            {
                "vault_path": "C:/Users/klee/KnowledgeVault",
                "state_path": "C:/Users/klee/AppData/Local/kb-win-sync/state/import-state.json",
                "log_path": "C:/Users/klee/AppData/Local/kb-win-sync/logs/kb-win-sync.log",
                "outlook": {"folders": []},
            }
        )
        self.assertEqual(config.folders, [])

    def test_parse_mailbox_selection(self) -> None:
        self.assertEqual(parse_mailbox_selection("1,2, 3,2", 5), [1, 2, 3])
        self.assertEqual(parse_mailbox_selection("", 5), [])
        with self.assertRaises(ValueError):
            parse_mailbox_selection("1,x", 5)
        with self.assertRaises(ValueError):
            parse_mailbox_selection("6", 5)

    def test_list_mailboxes_can_update_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                """vault_path: "D:/KnowledgeVault"
state_path: "state.json"
log_path: "log.txt"
outlook:
  folders:
    - name: "project-a"
      outlook_path: "\\\\Mailbox - User Name\\\\Inbox\\\\_KB\\\\ProjectA"
      target_folder: "20_Emails/ProjectA"
      tags:
        - "email"
        - "project/project-a"
      save_msg: false
      save_attachments: false
sync:
  enabled: false
""",
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                code = _append_folder_config_snippets(str(config_path), ["\\Mailbox\\Inbox\\_KB\\Real Project"])
            self.assertEqual(code, 0)
            updated = config_path.read_text(encoding="utf-8")
            self.assertIn('outlook_path: "\\\\Mailbox\\\\Inbox\\\\_KB\\\\Real Project"', updated)
            self.assertIn('target_folder: "20_Emails/real-project"', updated)
            self.assertIn("save_msg: false", updated)
            self.assertIn("save_attachments: false", updated)
            self.assertNotIn("Mailbox - User Name", updated)
            self.assertIn("updated config:", output.getvalue())

            with redirect_stdout(StringIO()):
                code = _append_folder_config_snippets(str(config_path), ["\\Mailbox\\Inbox\\_KB\\Real Project"])
            self.assertEqual(code, 0)
            self.assertEqual(config_path.read_text(encoding="utf-8").count("Real Project"), 1)

    def test_state_read_write_and_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(f"{tmp}/state.json")
            state = store.load()
            state.mark_imported("k1", "20_Emails/a.md")
            store.save(state)
            self.assertEqual(store.load().imported["k1"]["path"], "20_Emails/a.md")
            store.path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                store.load()

    def test_rendering_is_deterministic_and_valid_enough(self) -> None:
        email = EmailMessage(
            subject='Unsafe:/ subject with a very long title ' + "x" * 120,
            sender="Kim <kim@example.test>",
            to=["Hong <hong@example.test>"],
            received="2026-05-19T09:15:00+09:00",
            body="hello\n\n\nworld",
            folder="Inbox/_KB/ProjectA",
            conversation_id="conv",
            tags=["email"],
            attachments=[EmailAttachment("report.txt", "90_Attachments/email/key/report.txt")],
            original_msg="90_Attachments/email/key/original.msg",
        )
        self.assertEqual(sanitize_filename('a/b:c*?'), "a_b_c__")
        self.assertEqual(message_key(email), message_key(email))
        path = target_path(email, "20_Emails/ProjectA")
        self.assertTrue(path.endswith(f"__{message_key(email)}.md"))
        self.assertLess(len(path.split("/")[-1]), 140)
        md = render_markdown(email, "20_Emails/ProjectA", imported_at="2026-05-19T00:00:00+00:00")
        self.assertTrue(md.startswith("---\ntype:"))
        self.assertIn("# Unsafe:/ subject", md)
        self.assertIn("## Metadata", md)
        self.assertIn("## Body", md)
        self.assertIn("[[90_Attachments/email/key/report.txt]]", md)

    def test_artifact_saving_populates_markdown_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            def write_text(value: str):
                def saver(path: Path) -> None:
                    path.write_text(value, encoding="utf-8")

                return saver

            email = EmailMessage(
                subject="Artifacts",
                sender="Kim <kim@example.test>",
                received="2026-05-19T09:15:00+09:00",
                body="body",
                conversation_id="conv",
                message_id="message-id",
                attachments=[
                    EmailAttachment("report?.txt", saver=write_text("a")),
                    EmailAttachment("report?.txt", saver=write_text("b")),
                ],
                original_msg_saver=write_text("msg"),
            )
            saved, attachments_saved, msg_saved = save_email_artifacts(
                email,
                Path(tmp),
                save_msg=True,
                save_attachments=True,
            )
            key = message_key(email)
            self.assertEqual(attachments_saved, 2)
            self.assertEqual(msg_saved, 1)
            self.assertEqual(saved.attachments[0].saved_path, f"90_Attachments/email/{key}/report_.txt")
            self.assertEqual(saved.attachments[1].saved_path, f"90_Attachments/email/{key}/report_-2.txt")
            self.assertEqual(saved.original_msg, f"90_Attachments/email/{key}/original.msg")
            self.assertTrue((Path(tmp) / saved.attachments[0].saved_path).exists())
            self.assertTrue((Path(tmp) / saved.original_msg).exists())

    def test_run_import_dry_run_is_testable_without_outlook(self) -> None:
        class FakeClient:
            def count_folder_items(self, folder: OutlookFolderConfig) -> int:
                return 1

            def iter_folder_messages(self, folder: OutlookFolderConfig):
                self.folder = folder
                return [
                    EmailMessage(
                        subject="Dry run",
                        sender="Kim <kim@example.test>",
                        received="2026-05-19T09:15:00+09:00",
                        body="body",
                        message_id="dry-run-message",
                    )
                ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = WinConfig(
                vault_path=root / "vault",
                state_path=root / "state.json",
                log_path=root / "sync.log",
                folders=[
                    OutlookFolderConfig(
                        name="project-a",
                        outlook_path="\\Mailbox\\Inbox\\_KB\\ProjectA",
                        target_folder="20_Emails/ProjectA",
                    )
                ],
                sync=SyncConfig(enabled=False),
            )
            output = StringIO()
            with redirect_stdout(output):
                summary = run_import(
                    config,
                    FakeClient(),
                    dry_run=True,
                    folder_filter=None,
                    force=False,
                    config_path=str(root / "config.yaml"),
                )
            self.assertEqual(summary["scanned"], 1)
            self.assertEqual(summary["imported"], 0)
            self.assertIn("summary scanned=1 imported=0", output.getvalue())
            self.assertIn("next: kb-win-sync --config", output.getvalue())
            self.assertFalse(config.state_path.exists())

    def test_run_import_logs_progress_to_console_and_file(self) -> None:
        class FakeClient:
            def count_folder_items(self, folder: OutlookFolderConfig) -> int:
                return 1

            def iter_folder_messages(self, folder: OutlookFolderConfig):
                self.folder = folder

                def write_text(value: str):
                    def saver(path: Path) -> None:
                        path.write_text(value, encoding="utf-8")

                    return saver

                return [
                    EmailMessage(
                        subject="Real import",
                        sender="Kim <kim@example.test>",
                        received="2026-05-19T09:15:00+09:00",
                        body="body",
                        message_id="real-import-message",
                        attachments=[EmailAttachment("report.txt", saver=write_text("attachment"))],
                        original_msg_saver=write_text("msg"),
                    )
                ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = WinConfig(
                vault_path=root / "vault",
                state_path=root / "state.json",
                log_path=root / "sync.log",
                folders=[
                    OutlookFolderConfig(
                        name="project-a",
                        outlook_path="\\Mailbox\\Inbox\\_KB\\ProjectA",
                        target_folder="20_Emails/ProjectA",
                        save_msg=True,
                        save_attachments=True,
                    )
                ],
                sync=SyncConfig(enabled=False),
            )
            output = StringIO()
            with redirect_stdout(output):
                _configure_logging(config.log_path, verbose=False)
                summary = run_import(
                    config,
                    FakeClient(),
                    dry_run=False,
                    folder_filter=None,
                    force=False,
                    config_path=str(root / "config.yaml"),
                )
            self.assertEqual(summary["imported"], 1)
            console = output.getvalue()
            self.assertIn("Starting kb-win-sync import", console)
            self.assertIn("Scanning Outlook folder name=project-a", console)
            self.assertIn("total_items=1", console)
            self.assertIn("Processing message 1/1 folder=project-a", console)
            self.assertIn("Imported message key=", console)
            log_text = config.log_path.read_text(encoding="utf-8")
            self.assertIn("Import summary selected_folders=1", log_text)
            self.assertIn("Saved import state", log_text)

    def test_incremental_sync_manifest_tracks_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("one", encoding="utf-8")
            (root / ".kb-sync-manifest.json").write_text("{}", encoding="utf-8")
            plan, manifest = build_incremental_sync_plan(root, {})
            self.assertEqual([path.name for path in plan.files], ["a.md"])
            save_manifest(root / ".kb-sync-manifest.json", manifest)
            self.assertEqual(load_manifest(root / ".kb-sync-manifest.json"), manifest)

            plan, manifest = build_incremental_sync_plan(root, manifest)
            self.assertEqual(plan.files, [])
            (root / "a.md").write_text("two", encoding="utf-8")
            plan, manifest = build_incremental_sync_plan(root, manifest)
            self.assertEqual([path.name for path in plan.files], ["a.md"])


if __name__ == "__main__":
    unittest.main()
