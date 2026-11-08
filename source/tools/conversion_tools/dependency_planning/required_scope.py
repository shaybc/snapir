"""Expand qualified operation roots, stopping at trusted reusable service boundaries."""
from models.dependency_resolution_plan import DependencyResolutionPlan
from tools.operation_call_tools.ordering import operation_waves


def required_scope(graph, roots, lookup_service=None, *, excluded=()):
    """Return dependency-first source work and API boundaries without invoking a model.

    Channel/include filters select roots only. Explicit exclusions still prohibit
    source conversion; a published API may satisfy an excluded dependency.
    """
    roots, excluded = set(roots), set(excluded or ())
    result = DependencyResolutionPlan(requested_operations=sorted(roots))
    outgoing, issues = {}, {}
    for call in graph['calls']:
        outgoing.setdefault(call['caller'], []).append(call)
    for issue in graph['issues']:
        issues.setdefault(issue['operation'], []).append(issue)
    visited, required, source, edges, cycle_paths = set(), set(), set(), [], []
    pending = [(key, [key]) for key in sorted(roots, reverse=True)]
    while pending:
        key, path = pending.pop()
        required.add(key)
        result.operation_paths.setdefault(key, path)
        if key in path[:-1]:
            cycle_paths.append(path[path.index(key):])
            continue
        if key in visited:
            continue
        visited.add(key)
        if key.split('/', 1)[-1] in excluded or key in excluded:
            result.blockers.append(dict(kind='excluded_dependency', operation=key, path=path,
                detail='Required operation is explicitly excluded and has no reusable API: ' + key))
            continue
        if key not in graph['operations']:
            result.blockers.append(dict(kind='missing_evidence', operation=key, path=path,
                detail='Provide the mapped operation evidence for conversion.'))
            continue
        source.add(key)
        candidates = [(call, False) for call in outgoing.get(key, ())]
        for issue in issues.get(key, ()):
            target = issue.get('callee')
            if target:
                candidates.append((dict(issue, caller=key), True))
            else:
                result.blockers.append(dict(kind='unresolved_target', operation=key, path=path,
                    detail=issue['detail'], evidence=issue))
        for call, unresolved in sorted(candidates, key=lambda item: (item[0]['callee'], item[0].get('step', '')), reverse=True):
            target = call['callee']
            required.add(target)
            result.operation_paths.setdefault(target, path + [target])
            service = lookup_service(target) if lookup_service else None
            if service is not None:
                result.reused_services[target] = service.model_dump(mode='json') if hasattr(service, 'model_dump') else service
                continue
            if unresolved:
                result.blockers.append(dict(kind='unresolved_target', operation=key, path=path + [target],
                    detail=call['detail'], evidence=call))
                continue
            edges.append(dict(call, caller=key))
            pending.append((target, path + [target]))
    result.required_operations = sorted(required)
    result.source_operations = sorted(source)
    effective = dict(operations={key: {} for key in required}, calls=edges,
        issues=[dict(operation=item['path'][0]) for item in result.blockers])
    waves = operation_waves(effective)
    cycles = {}
    for key in sorted(source):
        group = waves[key]['cycle_group']
        if group:
            cycles.setdefault(group, []).append(key)
    for members in cycles.values():
        path = next(path for path in cycle_paths if path[0] in members)
        result.blockers.append(dict(kind='cycle', operation=members[0], path=path, members=members,
            detail='Operation dependency cycle requires coordinated contracts.'))
    result.order = sorted(source, key=lambda key: (waves[key]['wave'] is None, waves[key]['wave'] or 0, key))
    return result
