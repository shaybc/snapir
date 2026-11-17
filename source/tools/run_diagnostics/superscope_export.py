"""On-demand SuperScope export from saved converter evidence, without analysis or model calls."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3

import yaml
from tools.run_diagnostics.conversion_records import load_graph
from tools.run_diagnostics.superscope_model import build_model, focus_identity
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def export_model(directory, focus, output=None):
    """Create an isolated export; never overwrite a project model or an edited prior export."""
    directory = Path(directory).resolve()
    graph = load_graph(directory)
    identity = focus_identity(graph, focus)
    model, views, mapping, view = build_model(graph, identity)
    destination = Path(output).resolve() if output else directory / 'reports/superscope' / ('graph-' + digest(identity)[:16] + '-' + graph.snapshot_id[:12])
    if destination.exists():
        raise ValueError('Export destination already exists; choose a new --output folder to preserve prior models and layouts')
    destination.mkdir(parents=True)
    folder = destination / '.superscope'
    (folder / 'diagrams').mkdir(parents=True)
    (folder / 'model.yaml').write_text(yaml.safe_dump(model, sort_keys=False, allow_unicode=True), encoding='utf-8')
    for item in views:
        (folder / 'diagrams' / (item['id'] + '.yaml')).write_text(yaml.safe_dump(item, sort_keys=False), encoding='utf-8')
    (folder / 'view.yaml').write_text(yaml.safe_dump(view, sort_keys=False), encoding='utf-8')
    (destination / 'converter-records.json').write_text(graph.model_dump_json(indent=2), encoding='utf-8')
    manifest = dict(schema_version='conversion-superscope-v1', run_id=graph.run_id, snapshot_id=graph.snapshot_id,
        focus=identity, max_levels=4, display_objects=mapping,
        limitations=graph.issues, source='saved converter records only; no source scan or AI calls')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (destination / 'conversion.code-workspace').write_text(json.dumps(dict(folders=[dict(path='.')],
        settings={'superscope.modelFolder': '.superscope'}), indent=2), encoding='utf-8')
    (destination / 'README.txt').write_text('Open conversion.code-workspace in VS Code, then run SuperScope: Open Canvas.\n'
        'Double-click objects to enter their recorded dependency views. At level four, remaining descendants are flattened.\n'
        'Navigation aliases refer to canonical converter IDs in manifest.json. Labelled arrows, not display parents, describe source relationships.\n'
        'Missing records are unknown; component build/test success is separate from directional comparisons and operation acceptance.\n', encoding='utf-8')
    return destination


def main(argv=None):
    """Run explicitly copied dashboard commands; no conversion code is executed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--focus', required=True)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        print('SuperScope diagram: ' + str(export_model(args.run, args.focus, args.output)))
    except (OSError, ValueError, sqlite3.Error) as error:
        print('SuperScope export could not complete: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
