from __future__ import annotations

import argparse
import sys

from .config import load_config
from .diagnostics import smoke_test, status_lines, validate_config
from .indexer import reindex
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kb_api")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["reindex", "serve", "validate-config", "status", "smoke-test"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", required=True)
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
