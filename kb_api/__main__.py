from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .diagnostics import doctor_lines, smoke_test, status_lines, validate_config
from .enrichment import enrich_vault
from .indexer import reindex
from .server import serve
from .templates import LINUX_CONFIG_TEMPLATE


def _write_config_template(output_arg: str, *, force: bool) -> int:
    output = Path(output_arg)
    if output.exists() and not force:
        print(f"ERROR: config already exists: {output}", file=sys.stderr)
        print("Use --force to overwrite.", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(LINUX_CONFIG_TEMPLATE, encoding="utf-8")
    print(f"created config: {output}")
    print("next:")
    print(f"  1. edit {output}")
    print(f"  2. kb-api doctor --config {output}")
    print(f"  3. kb-api reindex --config {output}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_api")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["reindex", "serve", "validate-config", "status", "smoke-test", "doctor"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", required=True)
    enrich = sub.add_parser("enrich")
    enrich.add_argument("--config", required=True)
    enrich.add_argument("--use-cache-only", action="store_true")
    enrich.add_argument("--cline-command", default="cline")
    init = sub.add_parser("init-config")
    init.add_argument("--output", required=True)
    init.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init-config":
        return _write_config_template(args.output, force=args.force)
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
        print(f"next: kb-api serve --config {args.config}")
        print("verify: curl -sS 'http://127.0.0.1:8765/health?deep=true'")
        return 0
    if args.command == "enrich":
        try:
            stats = enrich_vault(config, use_cache_only=args.use_cache_only, cline_command=args.cline_command)
        except (RuntimeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(
            "enrich "
            f"raw_notes={stats.raw_notes} "
            f"enriched_notes={stats.enriched_notes} "
            f"copied_files={stats.copied_files} "
            f"failed={stats.failed}"
        )
        return 0 if stats.failed == 0 else 2
    if args.command == "serve":
        serve(config)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
