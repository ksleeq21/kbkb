from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


class CliUsabilityTests(unittest.TestCase):
    def run_cmd(self, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(args, cwd=Path(__file__).resolve().parents[1], env=merged_env, text=True, capture_output=True, timeout=10)

    def test_api_validate_status_and_smoke_test(self) -> None:
        env = {"KB_API_TOKEN": "test-token", "KB_API_ADMIN_TOKEN": "admin-token"}
        validate = self.run_cmd([sys.executable, "-m", "kb_api", "validate-config", "--config", "examples/linux-config.fixture.yaml"], env)
        self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)
        self.assertIn("config: ok", validate.stdout)

        smoke = self.run_cmd([sys.executable, "-m", "kb_api", "smoke-test", "--config", "examples/linux-config.fixture.yaml"], env)
        self.assertEqual(smoke.returncode, 0, smoke.stderr + smoke.stdout)
        self.assertIn("smoke-test: ok", smoke.stdout)
        self.assertIn("search: ok", smoke.stdout)

        status = self.run_cmd([sys.executable, "-m", "kb_api", "status", "--config", "examples/linux-config.fixture.yaml"], env)
        self.assertEqual(status.returncode, 0, status.stderr + status.stdout)
        self.assertIn("notes:", status.stdout)

        doctor = self.run_cmd([sys.executable, "-m", "kb_api", "doctor", "--config", "examples/linux-config.fixture.yaml"], env)
        self.assertEqual(doctor.returncode, 0, doctor.stderr + doctor.stdout)
        self.assertIn("doctor: kb_api", doctor.stdout)
        self.assertIn("next:", doctor.stdout)

    def test_console_script_entrypoints_are_declared(self) -> None:
        pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["kb-api"], "kb_api.__main__:main")
        self.assertEqual(scripts["kb-win-sync"], "kb_win_sync.__main__:main")

    def test_api_init_config_creates_file_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "config.yaml"
            result = self.run_cmd(
                [sys.executable, "-m", "kb_api", "init-config", "--output", str(output)],
                {"HOME": tmp, "SHELL": "/bin/bash"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("kb-api doctor", result.stdout)
            self.assertIn("ensured directories:", result.stdout)
            self.assertIn("added shell token exports:", result.stdout)
            text = output.read_text(encoding="utf-8")
            self.assertIn(f'vault_path: "{tmp}/kb/KnowledgeVault-Enriched"', text)
            self.assertTrue((Path(tmp) / "kb" / "KnowledgeVault-Enriched").is_dir())
            self.assertTrue((Path(tmp) / "kb" / "KnowledgeVault-Raw").is_dir())
            self.assertTrue((Path(tmp) / ".local" / "share" / "kb-api" / "enrichment-cache").is_dir())
            bashrc = Path(tmp) / ".bashrc"
            rc_text = bashrc.read_text(encoding="utf-8")
            self.assertIn("# >>> kb-api local tokens >>>", rc_text)
            self.assertIn("# kb-api local bearer tokens", rc_text)
            self.assertIn("export KB_API_TOKEN=", rc_text)
            self.assertIn("export KB_API_ADMIN_TOKEN=", rc_text)
            second = self.run_cmd([sys.executable, "-m", "kb_api", "init-config", "--output", str(output)])
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)

    def test_api_init_config_does_not_duplicate_existing_token_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc_path = Path(tmp) / ".zshrc"
            rc_path.write_text("# >>> kb-api local tokens >>>\nexport KB_API_TOKEN='existing'\n# <<< kb-api local tokens <<<\n", encoding="utf-8")
            output = Path(tmp) / "config.yaml"
            result = self.run_cmd(
                [sys.executable, "-m", "kb_api", "init-config", "--output", str(output)],
                {"HOME": tmp, "SHELL": "/bin/zsh"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("shell token exports already exist:", result.stdout)
            rc_text = rc_path.read_text(encoding="utf-8")
            self.assertEqual(rc_text.count("# >>> kb-api local tokens >>>"), 1)

    def test_api_commands_use_default_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".config" / "kb-api" / "config.yaml"
            init = self.run_cmd(
                [sys.executable, "-m", "kb_api", "init-config", "--output", str(config)],
                {"HOME": tmp, "SHELL": "/bin/bash", "KB_API_TOKEN": "test-token", "KB_API_ADMIN_TOKEN": "admin-token"},
            )
            self.assertEqual(init.returncode, 0, init.stderr + init.stdout)

            env = {"HOME": tmp, "KB_API_TOKEN": "test-token", "KB_API_ADMIN_TOKEN": "admin-token"}
            doctor = self.run_cmd([sys.executable, "-m", "kb_api", "doctor"], env)
            self.assertEqual(doctor.returncode, 0, doctor.stderr + doctor.stdout)
            self.assertIn("doctor: kb_api", doctor.stdout)

            enrich = self.run_cmd([sys.executable, "-m", "kb_api", "enrich", "--use-cache-only"], env)
            self.assertEqual(enrich.returncode, 0, enrich.stderr + enrich.stdout)
            self.assertIn("enrich raw_notes=0", enrich.stdout)

            reindex = self.run_cmd([sys.executable, "-m", "kb_api", "reindex"], env)
            self.assertEqual(reindex.returncode, 0, reindex.stderr + reindex.stdout)
            self.assertIn("indexed notes=0", reindex.stdout)

    def test_api_missing_default_config_gives_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cmd([sys.executable, "-m", "kb_api", "doctor"], {"HOME": tmp})
            self.assertEqual(result.returncode, 2)
            self.assertIn("config not found", result.stderr)
            self.assertIn("kb-api init-config --output", result.stderr)
            self.assertIn("--config <path>", result.stderr)

    def test_api_validate_reports_missing_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "bad.yaml"
            config.write_text(f'vault_path: "{tmp}/missing"\ndatabase_path: "{tmp}/kb.sqlite"\n', encoding="utf-8")
            result = self.run_cmd([sys.executable, "-m", "kb_api", "validate-config", "--config", str(config)])
            self.assertEqual(result.returncode, 2)
            self.assertIn("vault_path does not exist", result.stdout)

    def test_win_validate_and_status_do_not_need_outlook(self) -> None:
        validate = self.run_cmd([sys.executable, "-m", "kb_win_sync", "validate-config", "--config", "examples/windows-config.example.yaml"])
        self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)
        self.assertIn("config: ok", validate.stdout)

        status = self.run_cmd([sys.executable, "-m", "kb_win_sync", "status", "--config", "examples/windows-config.example.yaml"])
        self.assertEqual(status.returncode, 0, status.stderr + status.stdout)
        self.assertIn("configured_folders: 1", status.stdout)

        doctor = self.run_cmd([sys.executable, "-m", "kb_win_sync", "doctor", "--config", "examples/windows-config.example.yaml"])
        self.assertEqual(doctor.returncode, 0, doctor.stderr + doctor.stdout)
        self.assertIn("doctor: kb_win_sync", doctor.stdout)
        self.assertIn("Preview import", doctor.stdout)

    def test_win_init_config_creates_file_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "config.yaml"
            result = self.run_cmd([sys.executable, "-m", "kb_win_sync", "init-config", "--output", str(output)], {"USERPROFILE": tmp})
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("kb-win-sync doctor", result.stdout)
            self.assertIn("ensured directories:", result.stdout)
            text = output.read_text(encoding="utf-8")
            self.assertIn(f'vault_path: "{tmp}/KnowledgeVault"', text)
            self.assertIn("sync:", text)
            self.assertNotIn("Mailbox - User Name", text)
            self.assertTrue((Path(tmp) / "KnowledgeVault").is_dir())
            self.assertTrue((Path(tmp) / "AppData" / "Local" / "kb-win-sync" / "state").is_dir())
            self.assertTrue((Path(tmp) / "AppData" / "Local" / "kb-win-sync" / "logs").is_dir())
            doctor = self.run_cmd([sys.executable, "-m", "kb_win_sync", "doctor", "--config", str(output)])
            self.assertEqual(doctor.returncode, 0, doctor.stderr + doctor.stdout)
            self.assertIn("outlook.folders is empty", doctor.stdout)
            self.assertIn("list-mailboxes", doctor.stdout)
            import_result = self.run_cmd([sys.executable, "-m", "kb_win_sync", "--config", str(output), "--dry-run"])
            self.assertEqual(import_result.returncode, 2)
            self.assertIn("no Outlook folders configured", import_result.stderr)
            sync_result = self.run_cmd([sys.executable, "-m", "kb_win_sync", "--config", str(output), "--sync-only"])
            self.assertEqual(sync_result.returncode, 0, sync_result.stderr + sync_result.stdout)
            self.assertIn("Starting SFTP sync enabled=False", sync_result.stdout)
            self.assertIn("SFTP sync uploaded 0 files", sync_result.stdout)
            second = self.run_cmd([sys.executable, "-m", "kb_win_sync", "init-config", "--output", str(output)])
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)

    def test_skill_script_reports_missing_token_without_leaking_value(self) -> None:
        env = os.environ.copy()
        env.pop("KB_API_TOKEN", None)
        result = subprocess.run(
            [sys.executable, "cline_skill_obsidian_kb/scripts/kb_search.py", "SSO"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("KB_API_TOKEN is not set", result.stderr)


if __name__ == "__main__":
    unittest.main()
