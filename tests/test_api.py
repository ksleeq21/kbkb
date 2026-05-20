from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kb_api.config import ApiConfig, load_config
from kb_api.enrichment import enrich_vault, render_enriched_markdown, validate_llm_metadata
from kb_api.enrichment_providers import parse_metadata_json
from kb_api.frontmatter import parse_markdown
from kb_api.indexer import index_status, read_by_path, reindex, safe_relative_path, search
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
            self.assertIn(index_status(config).fts_tokenizer, {"trigram", "default"})
            results = search(config, "SSO")
            self.assertTrue(results[0]["path"].startswith("20_Emails/"))
            self.assertIn("sender", results[0])
            self.assertIn("received", results[0])
            self.assertIn("matched_fields", results[0])
            note = read_by_path(config, results[0]["path"])
            self.assertIn("Synthetic SSO", note["title"])
            self.assertTrue(search(config, "SSO", filters={"tag": "project/project-a"}))
            self.assertTrue(search(config, "SSO", filters={"after": "2026-05-19", "before": "2026-05-19"}))
            self.assertEqual(search(config, "SSO", filters={"tag": "missing"}), [])
            self.assertEqual(search(config, "SSO", filters={"before": "2026-01-01"}), [])
            with self.assertRaises(ValueError):
                safe_relative_path("../secret")
            with self.assertRaises(ValueError):
                safe_relative_path("/tmp/secret")

    def test_enrichment_uses_cached_json_and_preserves_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw")
            enriched = os.path.join(tmp, "enriched")
            cache = os.path.join(tmp, "cache")
            os.makedirs(os.path.join(raw, "20_Emails", "ProjectA"))
            os.makedirs(os.path.join(raw, "90_Attachments", "email", "abc"))
            raw_note = os.path.join(raw, "20_Emails", "ProjectA", "email.md")
            attachment = os.path.join(raw, "90_Attachments", "email", "abc", "report.txt")
            with open(raw_note, "w", encoding="utf-8") as fh:
                fh.write("---\ntype: \"email\"\ntags:\n  - \"email\"\nsubject: \"개발망 회의록\"\n---\n# 개발망 회의록\n본문")
            with open(attachment, "w", encoding="utf-8") as fh:
                fh.write("attachment")
            cache_file = os.path.join(cache, "20_Emails", "ProjectA", "email.metadata.json")
            os.makedirs(os.path.dirname(cache_file))
            with open(cache_file, "w", encoding="utf-8") as fh:
                fh.write('{"tags": ["개발망", "회의록"], "llm_tags": ["인프라"], "llm_summary": "요약"}')

            config = ApiConfig(
                vault_path=enriched,
                database_path=os.path.join(tmp, "kb.sqlite"),
                raw_vault_path=raw,
                enriched_vault_path=enriched,
                enrichment_cache_path=cache,
            )
            stats = enrich_vault(config, use_cache_only=True)
            self.assertEqual(stats.raw_notes, 1)
            self.assertEqual(stats.enriched_notes, 1)
            self.assertEqual(stats.copied_files, 1)
            with open(os.path.join(enriched, "20_Emails", "ProjectA", "email.md"), encoding="utf-8") as fh:
                self.assertIn('tags:\n  - "email"\n  - "개발망"\n  - "회의록"', fh.read())
            self.assertTrue(os.path.exists(os.path.join(enriched, "90_Attachments", "email", "abc", "report.txt")))
            with open(raw_note, encoding="utf-8") as fh:
                self.assertNotIn("llm_summary", fh.read())

    def test_enrichment_can_process_one_relative_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw")
            enriched = os.path.join(tmp, "enriched")
            cache = os.path.join(tmp, "cache")
            os.makedirs(os.path.join(raw, "20_Emails", "ProjectA"))
            os.makedirs(os.path.join(raw, "90_Attachments", "email", "abc"))
            first = os.path.join(raw, "20_Emails", "ProjectA", "first.md")
            second = os.path.join(raw, "20_Emails", "ProjectA", "second.md")
            attachment = os.path.join(raw, "90_Attachments", "email", "abc", "report.txt")
            with open(first, "w", encoding="utf-8") as fh:
                fh.write("---\ntype: \"email\"\ntags:\n  - \"email\"\nsubject: \"First\"\n---\n# First\n본문")
            with open(second, "w", encoding="utf-8") as fh:
                fh.write("---\ntype: \"email\"\ntags:\n  - \"email\"\nsubject: \"Second\"\n---\n# Second\n본문")
            with open(attachment, "w", encoding="utf-8") as fh:
                fh.write("attachment")
            cache_file = os.path.join(cache, "20_Emails", "ProjectA", "first.metadata.json")
            os.makedirs(os.path.dirname(cache_file))
            with open(cache_file, "w", encoding="utf-8") as fh:
                fh.write('{"tags": ["테스트"], "llm_summary": "단일 파일 테스트"}')

            config = ApiConfig(
                vault_path=enriched,
                database_path=os.path.join(tmp, "kb.sqlite"),
                raw_vault_path=raw,
                enriched_vault_path=enriched,
                enrichment_cache_path=cache,
            )
            stats = enrich_vault(config, use_cache_only=True, raw_file_path="20_Emails/ProjectA/first.md")

            self.assertEqual(stats.raw_notes, 1)
            self.assertEqual(stats.enriched_notes, 1)
            self.assertEqual(stats.copied_files, 0)
            self.assertEqual(stats.failed, 0)
            with open(os.path.join(enriched, "20_Emails", "ProjectA", "first.md"), encoding="utf-8") as fh:
                self.assertIn('llm_summary: "단일 파일 테스트"', fh.read())
            self.assertFalse(os.path.exists(os.path.join(enriched, "20_Emails", "ProjectA", "second.md")))
            self.assertFalse(os.path.exists(os.path.join(enriched, "90_Attachments", "email", "abc", "report.txt")))

    def test_enrichment_can_use_injected_metadata_provider(self) -> None:
        class FakeProvider:
            def __init__(self) -> None:
                self.calls = 0

            def generate_metadata(self, raw_markdown: str) -> dict:
                self.calls += 1
                self.raw_markdown = raw_markdown
                return {"tags": ["provider"], "llm_summary": "provider summary"}

        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw")
            enriched = os.path.join(tmp, "enriched")
            cache = os.path.join(tmp, "cache")
            os.makedirs(os.path.join(raw, "20_Emails", "ProjectA"))
            raw_note = os.path.join(raw, "20_Emails", "ProjectA", "email.md")
            with open(raw_note, "w", encoding="utf-8") as fh:
                fh.write("---\ntype: \"email\"\ntags:\n  - \"email\"\n---\n# Provider\n본문")

            provider = FakeProvider()
            config = ApiConfig(
                vault_path=enriched,
                database_path=os.path.join(tmp, "kb.sqlite"),
                raw_vault_path=raw,
                enriched_vault_path=enriched,
                enrichment_cache_path=cache,
            )
            stats = enrich_vault(config, metadata_provider=provider, raw_file_path="20_Emails/ProjectA/email.md")

            self.assertEqual(stats.enriched_notes, 1)
            self.assertEqual(provider.calls, 1)
            self.assertIn("# Provider", provider.raw_markdown)
            cache_file = os.path.join(cache, "20_Emails", "ProjectA", "email.metadata.json")
            with open(cache_file, encoding="utf-8") as fh:
                self.assertEqual(json.loads(fh.read())["tags"], ["provider"])

    def test_enrichment_rejects_unsafe_single_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw")
            os.makedirs(raw)
            config = ApiConfig(
                vault_path=os.path.join(tmp, "enriched"),
                database_path=os.path.join(tmp, "kb.sqlite"),
                raw_vault_path=raw,
                enriched_vault_path=os.path.join(tmp, "enriched"),
                enrichment_cache_path=os.path.join(tmp, "cache"),
            )
            with self.assertRaises(ValueError):
                enrich_vault(config, use_cache_only=True, raw_file_path="../outside.md")
            with self.assertRaises(ValueError):
                enrich_vault(config, use_cache_only=True, raw_file_path="/tmp/outside.md")
            with self.assertRaises(ValueError):
                enrich_vault(config, use_cache_only=True, raw_file_path="90_Attachments/email/report.txt")

    def test_cline_event_stream_parser_extracts_completion_result_text(self) -> None:
        stdout = "\n".join(
            [
                '{"type":"say","say":"text","text":"working"}',
                '{"type":"say","say":"completion_result","text":"```json\\n{\\n  \\"tags\\": [\\"BART\\"],\\n  \\"llm_summary\\": \\"BART 관련 이메일\\"\\n}\\n```"}',
            ]
        )
        self.assertEqual(parse_metadata_json(stdout), {"tags": ["BART"], "llm_summary": "BART 관련 이메일"})

    def test_cline_event_stream_parser_accepts_unfenced_completion_text(self) -> None:
        stdout = "\n".join(
            [
                '{"type":"say","say":"text","text":"working"}',
                '{"type":"say","say":"completion_result","text":"{\\"tags\\":[\\"BART\\"],\\"llm_tags\\":[\\"transit\\"]}"}',
            ]
        )
        self.assertEqual(parse_metadata_json(stdout), {"tags": ["BART"], "llm_tags": ["transit"]})

    def test_cline_event_stream_parser_accepts_messages_wrapper(self) -> None:
        stdout = (
            '{"messages": ['
            '{"type":"say","say":"text","text":"working"},'
            '{"type":"say","say":"completion_result","text":"```json\\n{\\"tags\\":[\\"BART\\"]}\\n```"}'
            ']}'
        )
        self.assertEqual(parse_metadata_json(stdout), {"tags": ["BART"]})

    def test_cline_event_stream_parser_extracts_json_from_extra_text(self) -> None:
        stdout = '{"type":"say","say":"completion_result","text":"Here is the JSON:\\n{\\"tags\\":[\\"BART\\"]}\\nDone."}'
        self.assertEqual(parse_metadata_json(stdout), {"tags": ["BART"]})

    def test_enrichment_rejects_source_metadata_changes(self) -> None:
        with self.assertRaises(ValueError):
            validate_llm_metadata({"conversation_id": "made-up"})
        with self.assertRaises(ValueError):
            validate_llm_metadata({"tags": ["../outside"]})
        with self.assertRaises(ValueError):
            validate_llm_metadata({"llm_tags": ["90_Attachments/email/report.txt"]})
        accepted = validate_llm_metadata({"tags": ["Project/Project A", "#회의록"]})
        self.assertEqual(accepted["tags"], ["project/project-a", "회의록"])
        enriched = render_enriched_markdown("---\ntype: \"email\"\ntags:\n  - \"email\"\n---\nBody", {"tags": ["회의록"]})
        self.assertIn('  - "email"\n  - "회의록"', enriched)

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
