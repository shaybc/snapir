"""Keep supporting Java inside format/step evidence instead of scheduling runtime replicas."""
from copy import deepcopy


def attach_supporting_sources(components):
    """Collapse verified supporting sources, retaining unresolved/external prerequisites and cycles."""
    generated_roles = {'step_implementation', 'format_leaf', 'format_wrapper', 'decorator'}
    supporting = {key for key, node in components.items() if node.kind == 'java_implementation'
                  and not generated_roles.intersection(node.roles)}
    for key, node in list(components.items()):
        if key in supporting:
            continue
        pending = list(reversed(node.dependencies))
        dependencies, evidence, visited = [], {}, set()
        while pending:
            target = pending.pop()
            if target in visited:
                continue
            visited.add(target)
            if target not in supporting:
                dependencies.append(target)
                continue
            source = components[target]
            evidence[target] = deepcopy(source.provenance)
            node.issues.extend(issue for issue in source.issues if issue not in node.issues)
            pending.extend(reversed(source.dependencies))
        if evidence:
            existing = {item['definition_id']: item for item in node.provenance.get('supporting_sources', [])}
            existing.update({item['definition_id']: item for item in evidence.values()})
            node.provenance['supporting_sources'] = [existing[item] for item in sorted(existing)]
        node.dependencies = dependencies
        node.dependency_reasons = {target: node.dependency_reasons.get(target,
            ['dependency reached through supporting source evidence']) for target in node.dependencies}
    # Shared runtime evidence follows each independently generated format/decorator.
    for node in components.values():
        if node.kind != 'format_node':
            continue
        for target in node.dependencies:
            implementation = components[target]
            if implementation.kind != 'java_implementation':
                continue
            evidence = {item['definition_id']: item for item in implementation.provenance.get('supporting_sources', [])}
            evidence.update({item['definition_id']: item for item in node.provenance.get('supporting_sources', [])})
            if evidence:
                implementation.provenance['supporting_sources'] = [evidence[item] for item in sorted(evidence)]
    for key in supporting:
        del components[key]
