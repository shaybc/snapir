"""Export a Mapper vault to Excel with streamed validation, progress and elapsed time."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.operation_call_tools.discovery import discover_operation_calls
from tools.operation_call_tools.ordering import operation_waves
from tools.operation_call_tools.export_progress import ExportProgress


def main(argv=None):
    """Read an existing Mapper vault and export a filterable planning workbook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--include-relationships', action='store_true')
    parser.add_argument('--node', help='Node executable; defaults to bundled runtime or PATH')
    parser.add_argument('--artifact-modules', help='node_modules containing @oai/artifact-tool')
    args = parser.parse_args(argv)
    if args.output.suffix.lower() != '.xlsx':
        parser.error('--output must end in .xlsx')
    progress = ExportProgress()
    progress.phase('Validating Mapper vault and discovering operation calls')
    graph = discover_operation_calls(args.vault, progress=progress.update)
    progress.phase('Calculating dependency waves')
    payload = dict(graph=graph, waves=operation_waves(graph), relationships=args.include_relationships)
    bundle = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
    node = args.node or (str(bundle / 'bin/node.exe') if (bundle / 'bin/node.exe').exists() else shutil.which('node'))
    if not node:
        parser.error('Node.js is required; specify --node')
    modules = args.artifact_modules or (str(bundle / 'node_modules') if (bundle / 'node_modules').is_dir() else '')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='operation-migration-') as temporary:
        data = Path(temporary) / 'graph.json'
        data.write_text(json.dumps(payload), encoding='utf-8')
        writer = Path(__file__).parent / 'tools/operation_call_tools/excel_report.mjs'
        progress.phase('Writing Excel workbook')
        subprocess.run([node, str(writer), str(data), str(args.output.resolve()), modules], check=True)
    print(f"Created {args.output}: {len(graph['operations'])} operations, {len(graph['calls'])} call sites, {len(graph['issues'])} issues. Elapsed={progress.elapsed()}", flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
