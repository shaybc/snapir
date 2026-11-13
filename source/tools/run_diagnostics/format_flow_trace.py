"""Extract format ownership evidence without exporting source, prompts, or model output."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from tools.run_diagnostics.ai_attempt_evidence import snapshot, journal, blob_reference, material_text, read_json
from tools.behavior_verification.format_lifecycle import basic_identity


def _fields(value, names):
    return {key: value[key] for key in names if key in value and isinstance(value[key], (str, int, bool, type(None)))}


def _json(text):
    try:
        value = json.loads(text or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _methods(value):
    """Export method identity only; never excerpts or ordering source text."""
    return _fields(value or {}, ('implementation_class', 'declaring_class', 'signature', 'method', 'returns'))


def _boundary(value):
    lifecycle = value.get('format_lifecycle') or {}
    return dict(**_fields(value, ('implementation_class', 'format_scope', 'analysis_status', 'kind')),
                issue_count=len(value.get('issues') or []), legacy_method=_methods(value.get('legacy_method')),
                direction=lifecycle.get('direction'),
                invocations=[_methods(item) for item in lifecycle.get('invocations', [])],
                framework_boundaries=[_methods(item) for item in value.get('framework_boundaries', [])])


def _request(value):
    """Whitelist identity metadata, excluding business configuration and code."""
    components = value.get('components') or {}
    return dict(**_fields(value, ('group_id', 'input_revision', 'kind', 'analysis_tool_hash')),
        components={key: dict(**_fields(node, ('label', 'kind')), unit_ids=node.get('unit_ids', []),
                             roles=node.get('roles', [])) for key, node in components.items() if isinstance(node, dict)},
        source_entry_points=value.get('source_entry_points', {}),
        format_lifecycles={key: [dict(direction=item.get('direction'),
            invocations=[_methods(call) for call in item.get('invocations', [])]) for item in items]
            for key, items in (value.get('format_lifecycles') or {}).items()})


def _safe_file(directory, path):
    return not path.is_symlink() and path.resolve().is_relative_to(directory)


def extract_format_flow(directory, implementation, diagnostics_directory=None, *, group_id=None):
    """Read raw evidence and diagnostics separately; do not infer runtime invocation."""
    directory = Path(directory).resolve()
    evidence = snapshot(directory)
    limitations = set(evidence['unavailable_tables'])
    plans, groups, members = [], {group_id} if group_id else set(), set()
    for row in evidence['conversion_component_plans']:
        plan = _json(row['plan_json'])
        group_members = {key for group in plan.get('groups', []) if group.get('group_id') == group_id
                         for key in group.get('members', [])} if group_id else None
        selected = {key: value for key, value in plan.get('components', {}).items()
                    if (key in group_members if group_id else value.get('label') == implementation)}
        members.update(selected)
        selected_groups = [item for item in plan.get('groups', []) if
                           (item.get('group_id') == group_id if group_id else set(item.get('members', [])) & set(selected))]
        groups.update(item['group_id'] for item in selected_groups)
        plans.append(dict(fingerprint=row.get('fingerprint'), components=_request(dict(components=selected))['components'],
                          groups=[dict(group_id=item['group_id'], members=item['members'],
                                       dependencies=item.get('dependencies', [])) for item in selected_groups]))

    def relevant(request, identity=''):
        if group_id:
            return (request.get('group_id') == group_id if request.get('group_id') else
                    identity == group_id or identity.startswith(group_id + ':'))
        return (request.get('group_id') in groups or identity in groups or
                any(identity.startswith(key + ':') for key in groups) or
                any(node.get('label') == implementation for node in (request.get('components') or {}).values()
                    if isinstance(node, dict)))

    attempts = []
    for table in ('behavior_attempts', 'staged_conversion_attempts'):
        for row in evidence[table]:
            request = _json(row.get('request_json'))
            if not relevant(request, row.get('identity', '')):
                continue
            groups.add(request.get('group_id') or row['identity'].split(':')[0])
            attempts.append(dict(table=table, **_fields(row, ('evidence_rowid', 'identity', 'category', 'stage',
                'fingerprint', 'revision', 'attempt', 'created_at', 'updated_at')),
                has_response=row.get('response') is not None, has_error=bool(row.get('error')),
                request_sha256=hashlib.sha256((row.get('request_json') or '').encode()).hexdigest(), request=_request(request)))
    captures = []
    selected_traces = set()
    events = journal(directory, limitations)
    for event in events:
        reference = blob_reference(event, 'request')
        if not reference:
            continue
        try:
            request = _json(material_text(directory, reference))
        except (OSError, ValueError):
            limitations.add('A captured request was unavailable or failed checksum verification.')
            continue
        if relevant(request, event.get('identity', '')):
            selected_traces.add(event.get('trace_id'))
            captures.append(dict(**_fields(event, ('trace_id', 'identity', 'fingerprint', 'event', 'timestamp')),
                                 request_sha256=reference['sha256'], request=_request(request)))
    timeline = [_fields(event, ('trace_id', 'delivery_id', 'identity', 'fingerprint', 'event', 'timestamp',
                 'attempt', 'http_status', 'usable_model_message')) for event in events
                if event.get('trace_id') in selected_traces and event.get('trace_id') is not None]
    boundaries, lookups, results, diagnostics = [], [], [], []
    components = {key: value for plan in plans for key, value in plan['components'].items()}
    for path in sorted(directory.glob('**/behavior_verification_boundaries.json')):
        if not _safe_file(directory, path):
            continue
        saved = read_json(path, {})
        basic = saved.get('basic_boundaries', {})
        parents = saved.get('boundaries', {})
        for key, boundary in basic.items():
            if boundary.get('implementation_class') in {node.get('label') for node in components.values()} | ({implementation} if implementation else set()):
                boundaries.append(dict(report=path.relative_to(directory).as_posix(), key=key, **_boundary(boundary)))
        for key, component in components.items():
            for unit in component['unit_ids']:
                lookup = basic_identity(unit, component.get('label') or implementation)
                lookups.append(dict(report=path.relative_to(directory).as_posix(), component_id=key, unit_id=unit,
                    basic_key=lookup, found=lookup in basic, basic=_boundary(basic[lookup]) if lookup in basic else None,
                    parent=_boundary(parents[unit]) if unit in parents else None))
    for path in sorted(directory.glob('**/component-generation.json')):
        if _safe_file(directory, path):
            for key, value in read_json(path, {}).get('groups', {}).items():
                if key in groups:
                    results.append(dict(report=path.relative_to(directory).as_posix(), group_id=key,
                                        **_fields(value, ('status', 'reused', 'validation_scope'))))
    diagnostic_root = Path(diagnostics_directory).resolve() if diagnostics_directory else directory
    diagnostic_paths = sorted(diagnostic_root.glob('**/conversion-ai-summary.json'))
    if not diagnostic_paths:
        limitations.add('No saved diagnostics summary found; supply --diagnostics if exported outside the run.')
    for path in diagnostic_paths:
        if _safe_file(diagnostic_root, path):
            for target in read_json(path, {}).get('targets', []):
                if target.get('identity') in groups:
                    displayed = dict(report=path.relative_to(diagnostic_root).as_posix(),
                        **_fields(target, ('identity', 'name', 'result', 'component_head_status')),
                        source_entry_points=target.get('source_entry_points', {}), attempts=[])
                    for attempt in target.get('attempts', []):
                        metadata = _fields(attempt, ('identity', 'fingerprint', 'category', 'number', 'timestamp', 'outcome'))
                        reference = (attempt.get('materials') or {}).get('request') or {}
                        exported = reference.get('exported_file')
                        if exported:
                            exported_path = path.parent / exported
                            if _safe_file(diagnostic_root, exported_path) and exported_path.is_file():
                                data = exported_path.read_bytes()
                                metadata['request_sha256'] = hashlib.sha256(data).hexdigest()
                                metadata['request'] = _request(_json(data.decode('utf-8-sig')))
                        displayed['attempts'].append(metadata)
                    diagnostics.append(displayed)
    receipts = _receipts(directory, groups, limitations)
    return dict(schema_version='format-flow-trace-v1', implementation=implementation, group_id=group_id, plans=plans,
        component_heads=[_fields(row, ('group_id', 'status', 'input_revision', 'contract_revision', 'result_revision'))
                         for row in evidence['conversion_component_heads'] if row['group_id'] in groups],
        basic_boundaries=boundaries, exact_boundary_lookups=lookups, database_attempts=attempts,
        captured_requests=captures, delivery_timeline=timeline, component_results=results,
        snapshots=[_fields(row, ('category', 'identity', 'fingerprint', 'status', 'updated_at'))
                   for row in evidence['behavior_snapshots'] if relevant({}, row.get('identity', ''))],
        validation_receipts=receipts, saved_diagnostics=diagnostics,
        limitations=sorted(limitations | {'Recorded entry metadata does not prove that the original method executed.',
            'Generated test success does not establish original-versus-native equivalence.',
            'Historical requests are not attributed to a reused result without matching receipt evidence.',
            'No raw logs, prompts, source, configuration values, model responses, or error bodies are exported.'}))


def _receipts(directory, groups, limitations):
    """Follow immutable result records to local receipts; never follow external artifact paths."""
    result = []
    with closing(sqlite3.connect((directory / 'state/migration.db').as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='conversion_component_records' AND type='table'").fetchone():
            limitations.add('Immutable component records are unavailable.')
            return result
        for row in conn.execute("SELECT * FROM conversion_component_records WHERE run_id=? AND category='result'", (directory.name,)):
            if row['group_id'] not in groups:
                continue
            record = _json(row['record_json'])
            for key, artifact in record.get('results', {}).items():
                entry = dict(group_id=row['group_id'], component_id=key, result_revision=row['revision'],
                    **_fields(artifact, ('input_revision', 'contract_revision', 'validation_scope', 'behavioral_equivalence')))
                path = Path(artifact.get('artifact_root', '')) / artifact.get('validation_report', '')
                if not path.is_absolute():
                    entry['receipt_state'] = 'relative artifact path; not resolved by guessing'
                elif not _safe_file(directory, path):
                    entry['receipt_state'] = 'artifact outside run; not read'
                elif not path.is_file():
                    entry['receipt_state'] = 'missing'
                else:
                    data = path.read_bytes()
                    entry.update(receipt_state='read', checksum_matches=hashlib.sha256(data).hexdigest() == artifact.get('validation_report_hash'))
                    receipt = _json(data.decode('utf-8-sig'))
                    entry.update(_fields(receipt, ('input_revision', 'contract_revision', 'validation_scope')))
                    entry['source_entry_points'] = receipt.get('source_entry_points', {})
                    validation = receipt.get('validation') or {}
                    entry['validation'] = _fields(validation, ('status', 'success', 'build_passed', 'compilation_passed', 'tests_passed', 'test_count', 'behavioral_equivalence')) if isinstance(validation, dict) else {}
                    comparison = receipt.get('format_comparison')
                    entry['comparison_status'] = _fields(comparison, ('status', 'behavioral_equivalence')) if isinstance(comparison, dict) else None
                result.append(entry)
    return result
