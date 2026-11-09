"""Select only a configured unit's reachable formats and verified Java dependencies."""


def format_evidence(closure, identity):
    """Follow child nodes and refFmt identities without importing sibling format roles."""
    pending, visited, classes, definitions = [closure.formats[identity]], set(), set(), {}
    while pending:
        node = pending.pop()
        if node.occurrence_id in visited:
            continue
        visited.add(node.occurrence_id)
        if node.java_class:
            classes.add(node.java_class)
        classes.update(item['java_class'] for item in node.decorators if item.get('java_class'))
        pending.extend(node.children)
        reference = node.reference_definition_id
        if reference and reference not in definitions:
            if reference not in closure.formats:
                raise ValueError('Selected unit references an unavailable format: ' + reference)
            definitions[reference] = closure.formats[reference]
            pending.append(closure.formats[reference])
    return classes, [node.model_dump(mode='json') for key, node in sorted(definitions.items()) if key != identity]


def java_evidence(closure, roots):
    """Traverse recorded syntax dependencies; never fall back to the operation-wide set."""
    origins = {item['fqcn']: item for item in closure.java_origins}
    pending, selected = list(roots), {}
    external = {item['class_name']: item for item in closure.external_dependencies}
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        origin = origins.get(name)
        if origin is None:
            if name in external:
                selected[name] = dict(fqcn=name, status='explicit_external', evidence=external[name])
                continue
            raise ValueError('Unit Java dependency is outside verified closure: ' + name)
        selected[name] = origin
        if origin['status'] == 'verified_source':
            if 'required_classes' not in origin:
                raise ValueError('Per-unit Java dependency graph is missing; refresh preparation')
            pending.extend(origin['required_classes'])
        elif origin['status'] not in {'explicit_replacement', 'verified_retention', 'verified_platform', 'evidence_dependency'}:
            raise ValueError('Unit Java dependency is unresolved: ' + name)
    records = [item for item in closure.external_dependencies if item['class_name'] in selected]
    return [selected[name] for name in sorted(selected)], records
