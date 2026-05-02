from __future__ import annotations

import argparse
from pathlib import Path

from .indexer import build_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Composer indexes")
    parser.add_argument("source", help="Directory containing Composer artifacts")
    parser.add_argument("--out", default="artifacts/indexes", help="Output root directory")
    parser.add_argument("--version", required=True, help="Schema/index version")
    args = parser.parse_args()

    out_dir = build_index(Path(args.source), Path(args.out), args.version)
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
