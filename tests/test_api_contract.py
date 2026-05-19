from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kb_api.config import ApiConfig
from kb_api.contract import CONTEXT_EVIDENCE_FIELDS, CONTRACT_VERSION, ERROR_FIELDS, NOTE_FIELDS, SEARCH_RESULT_FIELDS
from kb_api.indexer import reindex
from kb_api.server import serve


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.port = 8891
        cls.config = ApiConfig(
            vault_path=os.path.abspath("tests/fixtures/vault"),
            database_path=os.path.join(cls.tmp.name, "kb.sqlite"),
            port=cls.port,
        )
        reindex(cls.config)
        os.environ["KB_API_TOKEN"] = "contract-token"
        os.environ["KB_API_ADMIN_TOKEN"] = "contract-admin-token"
        cls.thread = threading.Thread(target=serve, args=(cls.config,), daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def api_json(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        data = json.dumps(body or {}).encode("utf-8") if body is not None else None
        req = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method,
            headers={"Authorization": "Bearer contract-token", "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_health_exposes_contract_version(self) -> None:
        with urlopen(f"http://127.0.0.1:{self.port}/health", timeout=5) as response:
            data = json.load(response)
        self.assertEqual(data["contract_version"], CONTRACT_VERSION)

    def test_search_response_contract(self) -> None:
        data = self.api_json("/search?q=SSO&limit=1")
        self.assertIn("results", data)
        self.assertTrue(data["results"])
        self.assertTrue(SEARCH_RESULT_FIELDS.issubset(data["results"][0].keys()))

    def test_note_response_contract(self) -> None:
        search_data = self.api_json("/search?q=SSO&limit=1")
        note_path = search_data["results"][0]["path"]
        data = self.api_json(f"/notes/by-path?path={note_path}")
        self.assertTrue(NOTE_FIELDS.issubset(data.keys()))

    def test_context_response_contract(self) -> None:
        data = self.api_json("/context", method="POST", body={"query": "SSO", "limit": 1})
        self.assertIn("evidence", data)
        self.assertTrue(data["evidence"])
        self.assertTrue(CONTEXT_EVIDENCE_FIELDS.issubset(data["evidence"][0].keys()))

    def test_error_response_contract(self) -> None:
        with self.assertRaises(HTTPError) as ctx:
            self.api_json("/search?q=")
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertIn("error", payload)
        self.assertTrue(ERROR_FIELDS.issubset(payload["error"].keys()))

    def test_skill_search_json_matches_contract(self) -> None:
        env = os.environ.copy()
        env["KB_API_BASE_URL"] = f"http://127.0.0.1:{self.port}"
        env["KB_API_TOKEN"] = "contract-token"
        result = subprocess.run(
            [sys.executable, "cline_skill_obsidian_kb/scripts/kb_search.py", "SSO", "--limit", "1", "--json"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(SEARCH_RESULT_FIELDS.issubset(data["results"][0].keys()))

    def test_skill_context_output_uses_contract_fields(self) -> None:
        env = os.environ.copy()
        env["KB_API_BASE_URL"] = f"http://127.0.0.1:{self.port}"
        env["KB_API_TOKEN"] = "contract-token"
        result = subprocess.run(
            [sys.executable, "cline_skill_obsidian_kb/scripts/kb_context.py", "SSO"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Evidence 1", result.stdout)
        self.assertIn("source:", result.stdout)
        self.assertIn("sender:", result.stdout)
        self.assertIn("received:", result.stdout)


if __name__ == "__main__":
    unittest.main()
