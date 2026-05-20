from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
import time
from pathlib import Path

from .config import ApiConfig, load_config, parse_config
from .diagnostics import doctor_lines, smoke_test, status_lines, validate_config
from .enrichment import enrich_vault
from .indexer import reindex
from .server import serve
from .templates import render_linux_config_template
from kb_win_sync.simple_yaml import load_simple_yaml


TOKEN_RC_BEGIN = "# >>> kb-api local tokens >>>"
TOKEN_RC_END = "# <<< kb-api local tokens <<<"
DEFAULT_CONFIG_PATH = Path("~/.config/kb-api/config.yaml")


def _default_config_path() -> Path:
    return DEFAULT_CONFIG_PATH.expanduser()


def _ensure_api_directories(config: ApiConfig) -> list[Path]:
    directories = {
        Path(config.vault_path),
        Path(config.database_path).parent,
    }
    if config.raw_vault_path is not None:
        directories.add(Path(config.raw_vault_path))
    if config.enriched_vault_path is not None:
        directories.add(Path(config.enriched_vault_path))
    if config.enrichment_cache_path is not None:
        directories.add(Path(config.enrichment_cache_path))
    ensured = sorted(directories)
    for directory in ensured:
        directory.mkdir(parents=True, exist_ok=True)
    return ensured


def _select_shell_rc_file(home: Path) -> Path:
    shell = Path(os.environ.get("SHELL", "")).name
    if shell == "bash":
        return home / ".bashrc"
    return home / ".zshrc"


def _ensure_shell_tokens(config: ApiConfig) -> tuple[Path, bool]:
    home = Path.home()
    rc_path = _select_shell_rc_file(home)
    existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    if TOKEN_RC_BEGIN in existing:
        return rc_path, False

    block = "\n".join(
        [
            "",
            TOKEN_RC_BEGIN,
            "# kb-api local bearer tokens for read-only search/context endpoints and admin reindex.",
            "# Keep these values private; rotate them if they are copied into logs, commits, or issues.",
            f"export {config.token_env}='{secrets.token_urlsafe(32)}'",
            f"export {config.admin_token_env}='{secrets.token_urlsafe(32)}'",
            TOKEN_RC_END,
            "",
        ]
    )
    with rc_path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    return rc_path, True


def _write_config_template(output_arg: str, *, force: bool) -> int:
    output = Path(output_arg)
    if output.exists() and not force:
        print(f"ERROR: config already exists: {output}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    config_text = render_linux_config_template()
    output.write_text(config_text, encoding="utf-8")
    config = parse_config(load_simple_yaml(config_text))
    ensured = _ensure_api_directories(config)
    rc_path, wrote_tokens = _ensure_shell_tokens(config)
    print(f"created config: {output}")
    print("ensured directories:")
    for directory in ensured:
        print(f"  {directory}")
    if wrote_tokens:
        print(f"added shell token exports: {rc_path}")
    else:
        print(f"shell token exports already exist: {rc_path}")
    print("next:")
    print(f"  1. restart your shell or run: source {rc_path}")
    print(f"  2. edit {output} if you need different vault paths")
    if output.expanduser() == _default_config_path():
        print("  3. kb-api doctor")
        print("  4. kb-api reindex")
    else:
        print(f"  3. kb-api doctor --config {output}")
        print(f"  4. kb-api reindex --config {output}")
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


def _load_config_or_report(config_arg: str | None) -> tuple[ApiConfig | None, Path, int]:
    path = Path(config_arg).expanduser() if config_arg else _default_config_path()
    if not path.exists():
        print(f"ERROR: config not found: {path}", file=sys.stderr)
        print(f"Run: kb-api init-config --output {path}", file=sys.stderr)
        print("Or pass: --config <path>", file=sys.stderr)
        return None, path, 2
    try:
        return load_config(path), path, 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: failed to load config: {path} ({exc})", file=sys.stderr)
        return None, path, 2


def _configure_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s", stream=sys.stderr, force=True)


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}m {remainder:.2f}s"


def _print_enrichment_summary(stats, *, elapsed_seconds: float, target_label: str) -> None:
    print(
        "enrich "
        f"raw_notes={stats.raw_notes} "
        f"enriched_notes={stats.enriched_notes} "
        f"copied_files={stats.copied_files} "
        f"failed={stats.failed}"
    )
    status = "SUCCESS" if stats.failed == 0 else "COMPLETED WITH FAILURES"
    marker = "✓" if stats.failed == 0 else "!"
    print("")
    print(f"{marker} Enrichment {status}")
    print("=" * 32)
    print(f"Target: {target_label}")
    print(f"Elapsed: {_format_elapsed(elapsed_seconds)}")
    print("")
    print("Results")
    print(f"  - Total Markdown files : {stats.raw_notes}")
    print(f"  - Succeeded            : {stats.enriched_notes}")
    print(f"  - Failed               : {stats.failed}")
    print(f"  - Copied non-Markdown  : {stats.copied_files}")
    if stats.failed:
        print("")
        print("Check stderr for ENRICH_FAILED entries.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_api")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["reindex", "serve", "validate-config", "status", "smoke-test", "doctor"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--config")
    enrich = sub.add_parser("enrich")
    enrich.add_argument("--config")
    enrich.add_argument("--use-cache-only", action="store_true")
    enrich.add_argument("--cline-command", default="cline")
    enrich_target = enrich.add_mutually_exclusive_group()
    enrich_target.add_argument("--file", help="raw_vault_path-relative Markdown file to enrich")
    enrich_target.add_argument("--folder", help="raw_vault_path-relative folder whose Markdown files should be enriched")
    enrich.add_argument("--verbose", action="store_true", help="show detailed enrichment debug logs")
    init = sub.add_parser("init-config")
    init.add_argument("--output", required=True)
    init.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init-config":
        return _write_config_template(args.output, force=args.force)
    config, config_path, code = _load_config_or_report(args.config)
    if config is None:
        return code
    if args.command == "validate-config":
        return _print_check_result(validate_config(config))
    if args.command == "status":
        print("\n".join(status_lines(config)))
        return 0
    if args.command == "doctor":
        lines, ok = doctor_lines(config)
        print("\n".join(lines))
        return 0 if ok else 2
    if args.command == "smoke-test":
        try:
            print("\n".join(smoke_test(config)))
            print("smoke-test: ok")
            print("next: kb-api init-config --output ~/.config/kb-api/config.yaml")
            return 0
        except RuntimeError as exc:
            print(str(exc))
            print("smoke-test: failed", file=sys.stderr)
            return 2
    if args.command == "reindex":
        stats = reindex(config)
        print(f"indexed notes={stats.notes} chunks={stats.chunks}")
        print(f"next: kb-api serve --config {config_path}")
        print("verify: curl -sS 'http://127.0.0.1:8765/health?deep=true'")
        return 0
    if args.command == "enrich":
        _configure_logging(verbose=args.verbose)
        started_at = time.monotonic()
        try:
            stats = enrich_vault(
                config,
                use_cache_only=args.use_cache_only,
                cline_command=args.cline_command,
                raw_file_path=args.file,
                raw_folder_path=args.folder,
                verbose=args.verbose,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if args.file:
            target_label = f'file "{args.file}"'
        elif args.folder:
            target_label = f'folder "{args.folder}"'
        else:
            target_label = "all raw Markdown files"
        _print_enrichment_summary(stats, elapsed_seconds=time.monotonic() - started_at, target_label=target_label)
        return 0 if stats.failed == 0 else 2
    if args.command == "serve":
        serve(config)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
