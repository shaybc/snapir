"""Read saved converter evidence only; never inspect source, run an analyzer or call AI."""
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime

from models.conversion_graph import ConversionGraph
from tools.conversion_tools.conversion_graph_records import graph_from_records, boundary_revision
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def _json(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def _database(directory):
    candidates = [directory / 'state/migration.db']
    if directory.parent.name == 'operation_workflows':
        candidates.append(directory.parent.parent / 'state/migration.db')
    return next((path for path in candidates if path.is_file()), None)


def load_graph(directory):
    """Prefer the converter snapshot; older runs expose only facts their saved records contain."""
    directory = Path(directory).resolve()
    snapshot = directory / 'state/conversion-graph.json'
    if snapshot.is_file():
        raw = snapshot.read_bytes()
        graph = ConversionGraph.model_validate_json(raw)
        activity = _json(directory / 'state/run_activity.json', {})
        if graph.recorded_at and activity.get('last_resumed_at') and datetime.fromisoformat(activity['last_resumed_at']) > datetime.fromisoformat(graph.recorded_at):
            raise ValueError('A newer resume has no matching converter graph yet; an older success will not be shown as current.')
        generation = directory / 'reports/3_dependency_closure_and_component_conversion/component-generation.json'
        pin = next((item.get('content_hash') for item in graph.evidence if item.get('record') == 'component_generation'), None)
        if pin and generation.is_file() and digest(_json(generation, {})) != pin:
            raise ValueError('The converter graph predates the current component report. Rerun diagnostics after recording completes; an older success will not be shown as current.')
        boundary_file = generation.parent / 'behavior_verification_boundaries.json'
        boundary_pin = next((item.get('content_hash') for item in graph.evidence if item.get('record') == 'boundary_report'), None)
        if boundary_pin and boundary_file.is_file() and boundary_file.stat().st_mtime_ns > snapshot.stat().st_mtime_ns and boundary_revision(_json(boundary_file, {})) != boundary_pin:
            raise ValueError('The converter graph predates the current entry-point records; rerun diagnostics after recording completes.')
        graph.evidence.append(dict(record='converter_graph', file=str(snapshot),
            sha256=hashlib.sha256(raw).hexdigest()))
    else:
        stage = directory / 'reports/3_dependency_closure_and_component_conversion'
        preparation = _json(directory / 'state/standalone-preparation.json', {})
        if not preparation:
            preparation = _json(stage / 'scoped_workflow_preparation.json', {})
        plan = preparation.get('component_plan')
        database = _database(directory)
        if plan is None and database and directory.parent.name != 'operation_workflows':
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
                conn.execute('PRAGMA query_only=ON')
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='conversion_component_plans'").fetchone():
                    rows = conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?', (directory.name,)).fetchall()
                    if len(rows) == 1:
                        plan = json.loads(rows[0][0])
        boundaries = preparation.get('boundaries') or _json(stage / 'behavior_verification_boundaries.json', {})
        report = _json(stage / 'component-generation.json', {})
        graph = graph_from_records(directory.name, plan or {}, boundaries, {}, report)
        graph.issues.append('Older run: structured conversion trace was not recorded; missing facts remain not recorded.')
        if not graph.nodes:
            graph.issues.append('No saved component plan or resolved class records were found.')
    database = _database(directory)
    if database:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
            conn.execute('PRAGMA query_only=ON')
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_workflow_progress'").fetchone():
                rows = conn.execute('SELECT operation_key,status,phase FROM operation_workflow_progress WHERE run_id=?', (graph.run_id,)).fetchall()
                for label, status, phase in rows:
                    for node in graph.nodes.values():
                        if node['kind'] == 'operation' and node['label'] == label:
                            node.update(workflow_status=status, workflow_phase=phase)
                            node['evidence'].append(dict(record='operation_workflow_progress', operation_key=label))
    graph.snapshot_id = digest(graph.model_dump(mode='json', exclude={'snapshot_id', 'recorded_at'}))
    return graph


def recorded_scopes(directory):
    """Keep per-operation snapshots separate so shared class names cannot mix runs or scopes."""
    root = Path(directory).resolve()
    scopes = [root] if (root / 'state/conversion-graph.json').is_file() or not (root / 'operation_workflows').is_dir() else []
    scopes.extend(path.parent.parent for path in sorted((root / 'operation_workflows').glob('*/state/conversion-graph.json')))
    return scopes or [root]
