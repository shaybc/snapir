"""Check native conversion scope against mapped calls and trusted published APIs."""

import json
from pathlib import Path

from tools.converted_service_registry_tools.location import resolve_registry_settings
from tools.converted_service_registry_tools.registry import open_registry, get_service
from tools.operation_call_tools.ordering import operation_waves
from tools.state_store_tools.operation_calls import load_graph


def check_dependencies(graph, selected, lookup_service):
    """Return scope blockers and reused contracts without changing scope or contacting services.

    Lookup receives a channel-qualified identity. Published boundaries are trusted;
    their source issues and internal calls are deliberately not traversed.
    """
    selected = set(selected)
    blockers, reused, evidence, visited = [], {}, [], set()
    outgoing = {}
    issues = {}
    for call in graph['calls']:
        outgoing.setdefault(call['caller'], []).append(call)
    for issue in graph['issues']:
        issues.setdefault(issue['operation'], []).append(issue)
    # Reuse existing graph calculations for cycle membership; report actual paths below.
    waves = operation_waves(graph)
    for start in sorted(selected):
        pending = [(start, [start])]
        while pending:
            node, path = pending.pop()
            if node in path[:-1]:
                blockers.append(dict(kind='cycle', path=path[path.index(node):-1] + [node],
                                     detail='Resolve this operation dependency cycle before planning.'))
                continue
            if node in visited:
                continue
            visited.add(node)
            if node not in graph['operations']:
                blockers.append(dict(kind='missing_evidence', operation=node, path=path,
                                     detail='Provide the mapped operation evidence for conversion.'))
                continue
            for issue in issues.get(node, []):
                target = issue.get('callee')
                if target:
                    evidence.append(dict(issue, caller=node))
                    service = lookup_service(target) if target not in selected else None
                    if service is not None:
                        reused[target] = service.model_dump(mode='json')
                        continue
                blockers.append(dict(kind='unresolved_target', operation=node, path=path + ([target] if target else []),
                                     detail=issue['detail'], evidence=issue))
            for call in sorted(outgoing.get(node, []), key=lambda item: (item['callee'], item['step']), reverse=True):
                evidence.append(call)
                target = call['callee']
                if target not in selected:
                    service = lookup_service(target)
                    if service is not None:
                        reused[target] = service.model_dump(mode='json')
                        continue
                    blockers.append(dict(kind='missing_dependency', operation=target, path=path + [target],
                                         detail='Include this required operation in the conversion scope.', evidence=call))
                pending.append((target, path + [target]))
    return dict(selected=sorted(selected), blockers=blockers, reused_services=reused,
                call_evidence=evidence, cyclic_operations=sorted({node for item in blockers
                    if item['kind'] == 'cycle' for node in item['path'] if waves[node]['cycle_group']}))


def run_intake_preflight(conn, config, profile, directory):
    """Save intake's dependency result in its existing run database and readable reports.

    Opens only the application's shared registry alongside the existing run connection.
    API address selection/pinning and approval are later planning responsibilities.
    """
    graph = load_graph(conn, config.run_id)
    if graph is None:
        raise ValueError('Mapped operation graph is required for dependency preflight')
    selected = [row[0] + '/' + row[1] for row in conn.execute(
        'SELECT channel,operation_id FROM operations WHERE run_id=? ORDER BY channel,operation_id', (config.run_id,))]
    application_id, registry_path = resolve_registry_settings(profile)
    registry = open_registry(registry_path)
    try:
        def lookup(key):
            channel, operation = key.split('/', 1)
            return get_service(registry, application_id, channel, operation)
        report = check_dependencies(graph, selected, lookup)
    finally:
        registry.close()
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
        raise ValueError('Dependency preflight is blocked; include or resolve required operations before planning')
