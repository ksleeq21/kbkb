from __future__ import annotations

import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kb_api.config import ApiConfig, load_config
from kb_api.frontmatter import parse_markdown
from kb_api.indexer import read_by_path, reindex, safe_relative_path, search
from kb_api.scanner import scan_markdown
from kb_api.server import serve


class ApiTests(unittest.TestCase):
    def test_linux_config_and_scanner(self) -> None:
        config = load_config("examples/linux-config.example.yaml")
        self.assertEqual(config.host, "127.0.0.1")
        files = scan_markdown("tests/fixtures/vault", [".obsidian", ".trash"])
        self.assertEqual(len(files), 2)

    def test_frontmatter_with_and_without_yaml(self) -> None:
        parsed = parse_markdown("---\ntype: \"note\"\ntags:\n  - \"x\"\n---\n# Hi")
        self.assertEqual(parsed.metadata["type"], "note")
        self.assertEqual(parsed.metadata["tags"], ["x"])
        self.assertEqual(parse_markdown("# Hi").metadata, {})

    def test_reindex_search_read_and_path_defense(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = ApiConfig(vault_path=os.path.abspath("tests/fixtures/vault"), database_path=os.path.join(tmp, "kb.sqlite"))
            stats = reindex(config)
            self.assertEqual(stats.notes, 2)
            self.assertGreaterEqual(stats.chunks, 2)
            results = search(config, "SSO")
            self.assertTrue(results[0]["path"].startswith("20_Emails/"))
            self.assertIn("sender", results[0])
            self.assertIn("received", results[0])
            self.assertIn("matched_fields", results[0])
            note = read_by_path(config, results[0]["path"])
            self.assertIn("Synthetic SSO", note["title"])
            with self.assertRaises(ValueError):
                safe_relative_path("../secret")
            with self.assertRaises(ValueError):
                safe_relative_path("/tmp/secret")

    def test_http_auth_health_search_and_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = ApiConfig(vault_path=os.path.abspath("tests/fixtures/vault"), database_path=os.path.join(tmp, "kb.sqlite"), port=8876)
            reindex(config)
            os.environ["KB_API_TOKEN"] = "test-token"
            thread = threading.Thread(target=serve, args=(config,), daemon=True)
            thread.start()
            health = urlopen("http://127.0.0.1:8876/health", timeout=5).read()
            self.assertIn(b'"status": "ok"', health)
            self.assertIn(b'"contract_version": "v1"', health)
            with self.assertRaises(HTTPError):
                urlopen("http://127.0.0.1:8876/search?q=SSO", timeout=5)
            req = Request("http://127.0.0.1:8876/search?q=SSO", headers={"Authorization": "Bearer test-token"})
            self.assertIn(b"20_Emails", urlopen(req, timeout=5).read())
            self.assertIn(b"database_exists", urlopen("http://127.0.0.1:8876/health?deep=true", timeout=5).read())


if __name__ == "__main__":
    unittest.main()
