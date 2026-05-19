from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .diagnostics import doctor_lines, smoke_test, status_lines, validate_config
from .indexer import reindex
from .server import serve
from .templates import LINUX_CONFIG_TEMPLATE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_api")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["reindex", "serve", "validate-config", "status", "smoke-test", "doctor"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", required=True)
    init = sub.add_parser("init-config")
    init.add_argument("--output", required=True)
    init.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init-config":
        output = Path(args.output)
        if output.exists() and not args.force:
            print(f"ERROR: config already exists: {output}", file=sys.stderr)
            print("Use --force to overwrite.", file=sys.stderr)
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(LINUX_CONFIG_TEMPLATE, encoding="utf-8")
        print(f"created config: {output}")
        print(f"next: edit {output}")
        print(f"next: python3 -m kb_api validate-config --config {output}")
        return 0
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
    if args.command == "smoke-test":
        try:
            print("\n".join(smoke_test(config)))
            print("smoke-test: ok")
            return 0
        except RuntimeError as exc:
            print(str(exc))
            print("smoke-test: failed", file=sys.stderr)
            return 2
    if args.command == "reindex":
        stats = reindex(config)
        print(f"indexed notes={stats.notes} chunks={stats.chunks}")
        return 0
    if args.command == "serve":
        serve(config)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
