from __future__ import annotations

import argparse
from pathlib import Path

from .indexer import build_index
from .pipeline import run_conversion_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Composer artifacts")
    sub = parser.add_subparsers(dest="command")

    index_parser = sub.add_parser("index", help="Build indexing artifacts")
    index_parser.add_argument("source", help="Directory containing Composer artifacts")
    index_parser.add_argument("--out", default="artifacts/indexes", help="Output root directory")
    index_parser.add_argument("--version", required=True, help="Schema/index version")

    pipeline_parser = sub.add_parser("pipeline", help="Run end-to-end Java conversion pipeline")
    pipeline_parser.add_argument("source", help="Directory containing Composer artifacts")
    pipeline_parser.add_argument("--out", default="artifacts/indexes", help="Output root directory")
    pipeline_parser.add_argument("--version", required=True, help="Schema/index version")

    args = parser.parse_args()

    command = args.command or "index"
    if command == "pipeline":
        out_dir = run_conversion_pipeline(Path(args.source), Path(args.out), args.version)
    else:
        out_dir = build_index(Path(args.source), Path(args.out), args.version)

    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
