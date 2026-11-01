"""Adapt component prerequisites to the existing deterministic, iterative SCC ordering."""
from tools.operation_call_tools.ordering import operation_waves
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from models.component_conversion_group import ComponentConversionGroup


def order_component_groups(components):
    """Return dependency-first coordinated groups; unresolved nodes block their dependents."""
    calls=[dict(caller=key,callee=dependency) for key,node in sorted(components.items()) for dependency in node.dependencies]
    if any(call['callee'] not in components for call in calls): raise ValueError('Component dependency has no planning node')
    graph=dict(operations=components,calls=calls,
        issues=[dict(operation=key) for key,node in components.items() if node.status=='unresolved' or node.issues])
    waves=operation_waves(graph)
    structural=operation_waves(dict(graph,issues=[])) if graph['issues'] else waves
    grouped={}
    for key,item in waves.items(): grouped.setdefault(item['cycle_group'] or key,[]).append(key)
    identities={key:'component-group-'+digest(sorted(members)) for members in grouped.values() for key in members}
    result=[]
    for members in grouped.values():
        members=sorted(members)
        cyclic=bool(waves[members[0]]['cycle_group'])
        wave=waves[members[0]]['wave']
        result.append(ComponentConversionGroup(group_id=identities[members[0]],members=members,
            dependencies=sorted({identities[target] for member in members for target in components[member].dependencies if target not in members}),
            wave=wave,cyclic=cyclic,reason='Unresolved prerequisite evidence' if wave is None else
            'Strongly connected dependencies must stay together' if cyclic else 'Recorded dependencies precede this component'))
    return sorted(result,key=lambda group:(group.wave is None,structural[group.members[0]]['wave'],group.group_id))
