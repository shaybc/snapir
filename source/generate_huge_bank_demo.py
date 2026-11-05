"""Generate a scalable local Bank Demo without changing the original fixture."""

import argparse
from pathlib import Path

from tools.huge_bank_demo.generation import generate_demo


def main():
    """Create or grow the generated fixture; counts are minimum total fixture files."""
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=int, default=1000, help='Minimum total files, rounded up to complete operation families (default: 1000)')
    parser.add_argument('--source', type=Path, default=repository / 'bank-demo')
    parser.add_argument('--output', type=Path, default=repository / 'huge-bank-demo')
    args = parser.parse_args()
    try:
        report = generate_demo(args.source, args.output, args.files)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Generation error: {exc}\n')
    print(f"Ready: {report['files']} files; {report['operations']} operations; {report['op_step_occurrences']} OP-step occurrences; {report['java_files']} Java files.", flush=True)
    print(f'Source workspace: {args.output.resolve() / "composer/Workspace"}', flush=True)
    print('Example selection: INTERNET / GetClientOverviewOpHuge00001 (includes its copied prerequisites).', flush=True)


if __name__ == '__main__':
    main()
