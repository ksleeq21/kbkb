from __future__ import annotations

import json
import tempfile
import unittest

from kb_win_sync.config import load_config, parse_config
from kb_win_sync.email_model import EmailAttachment, EmailMessage
from kb_win_sync.render import message_key, render_markdown, sanitize_filename, target_path
from kb_win_sync.state import ImportState, StateStore


class WinSyncTests(unittest.TestCase):
    def test_windows_config_parses_example(self) -> None:
        config = load_config("examples/windows-config.example.yaml")
        self.assertEqual(config.folders[0].name, "project-a")
        self.assertTrue(config.folders[0].save_msg)
        self.assertFalse(config.sync.enabled)

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


if __name__ == "__main__":
    unittest.main()
