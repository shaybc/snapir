"""Check native conversion scope against mapped calls and trusted published APIs."""

import json
from pathlib import Path

from tools.converted_service_registry_tools.location import resolve_registry_settings
from tools.converted_service_registry_tools.registry import open_registry, get_service
from tools.state_store_tools.operation_calls import load_graph


def check_dependencies(graph, selected, lookup_service, *, excluded=()):
    """Expand requested roots automatically; stop at compatible published APIs.

    Missing/ambiguous evidence and explicit exclusions remain blockers. Omitted
    channel/include selections never turn an available dependency into a blocker.
    """
    from tools.conversion_tools.dependency_planning.required_scope import required_scope
    roots = set(selected)
    scope = required_scope(graph, roots, lambda key: lookup_service(key) if key not in roots else None, excluded=excluded)
    evidence = [call for call in graph['calls'] if call['caller'] in scope.source_operations]
    evidence.extend(dict(issue, caller=issue['operation']) for issue in graph['issues']
                    if issue['operation'] in scope.source_operations and issue.get('callee'))
    return dict(requested=scope.requested_operations, selected=sorted(roots | set(scope.source_operations)),
                blockers=scope.blockers, reused_services=scope.reused_services, call_evidence=evidence,
                cyclic_operations=sorted({node for item in scope.blockers if item['kind'] == 'cycle'
                                          for node in item['members']}))


def run_intake_preflight(conn, config, profile, directory):
    """Save intake's dependency result in its existing run database and readable reports.

    Opens only the application's shared registry alongside the existing run connection.
    API address selection/pinning and approval are later planning responsibilities.
    """
    graph = load_graph(conn, config.run_id)
    if graph is None:
        raise ValueError('Mapped operation graph is required for dependency preflight')
    from tools.state_store_tools.dependency_scope import requested_operations, include_required_operations
    selected = requested_operations(conn, config)
    application_id, registry_path = resolve_registry_settings(profile)
    registry = open_registry(registry_path)
    try:
        def lookup(key):
            channel, operation = key.split('/', 1)
            return get_service(registry, application_id, channel, operation)
        report = check_dependencies(graph, selected, lookup, excluded=getattr(config, 'exclude_operations', ()))
    finally:
        registry.close()
    include_required_operations(conn, config, graph, report['selected'])
    selected = report['selected']
    from tools.state_store_tools.operation_calls import get_contract
    for key in selected:
        if key not in graph['operations'] or not graph['operations'][key].get('ref_formats'):
            continue
        try:
            contract = get_contract(conn, config.run_id, key)
            missing = [item['name'] for item in contract['formats'].values() if item.get('unresolved')]
            if missing:
                raise ValueError('Provide required mapped format evidence: ' + ', '.join(sorted(missing)))
        except ValueError as exc:
            report['blockers'].append(dict(kind='missing_evidence', operation=key, path=[key], detail=str(exc)))
    if not selected:
        report['blockers'].append(dict(kind='empty_scope', path=[], detail='Select operations to convert.'))
    conn.execute('CREATE TABLE IF NOT EXISTS operation_dependency_preflights (run_id TEXT PRIMARY KEY, report_json TEXT NOT NULL)')
    with conn:
        conn.execute('INSERT OR REPLACE INTO operation_dependency_preflights VALUES (?,?)',
                     (config.run_id, json.dumps(report, sort_keys=True)))
    folder = Path(directory) / 'reports' / '1_intake_and_legacy_analysis'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'dependency_preflight.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# Operation dependency preflight', '', 'Blocked' if report['blockers'] else 'Dependencies satisfied', '']
    lines.extend('- ' + ' -> '.join(item['path']) + ': ' + item['detail'] for item in report['blockers'])
    lines.extend('- Reuse published service: ' + key + ' (revision ' + value['api_revision'] + ')'
                 for key, value in sorted(report['reused_services'].items()))
    (folder / 'dependency_preflight.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def require_preflight_passed(conn, run_id):
    """Reject recorded dependency blockers before planning, retaining older run compatibility."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_dependency_preflights'").fetchone():
        return
    row = conn.execute('SELECT report_json FROM operation_dependency_preflights WHERE run_id=?', (run_id,)).fetchone()
    if row and json.loads(row[0])['blockers']:
        raise ValueError('Dependency preflight is blocked; resolve its dependency evidence before planning')
