"""Plan dependency-first conversion and library builds without overriding ownership."""

import heapq


def dependency_first_order(nodes, dependencies):
    """Return a topological order, rejecting cycles rather than choosing arbitrary order."""
    nodes = set(nodes)
    remaining = {node: set(dependencies.get(node, [])) & nodes for node in nodes}
    callers = {}
    for caller, targets in remaining.items():
        for target in targets:
            callers.setdefault(target, set()).add(caller)
    ready = [node for node, targets in remaining.items() if not targets]
    heapq.heapify(ready)
    result = []
    while ready:
        node = heapq.heappop(ready)
        result.append(node)
        for caller in callers.get(node, []):
            remaining[caller].remove(node)
            if not remaining[caller]:
                heapq.heappush(ready, caller)
    if len(result) != len(nodes):
        raise ValueError("Dependency cycle involving " + min(node for node, targets in remaining.items() if targets))
    return result


def plan_dependency_order(graph, assignments, definition_implementations=None):
    """Check reachable source issues and cross-project visibility; never change thresholds."""
    relevant = set(assignments)
    dependencies = {}
    library_dependencies = {owner: set() for owner in assignments.values() if owner}
    aliases = {}
    for key, implementation in (definition_implementations or {}).items():
        if implementation and key in relevant:
            aliases.setdefault(implementation, set()).add(key)
    for key in relevant:
        if key.startswith("implementation:"):
            aliases.setdefault(key.removeprefix("implementation:"), set()).add(key)
    issues = [issue.message for issue in graph.issues if issue.implementation_id in aliases]
    for edge in graph.dependencies:
        caller = "implementation:" + edge.caller_implementation_id
        target = "implementation:" + edge.target_implementation_id
        callers = aliases.get(edge.caller_implementation_id, set())
        if not callers or target not in relevant:
            continue
        for caller in callers:
            dependencies.setdefault(caller, set()).add(target)
            source_library, target_library = assignments[caller], assignments[target]
            if source_library and not target_library:
                issues.append("Shared library depends on operation-local source: " + caller + " -> " + target)
            elif source_library and target_library and source_library != target_library:
                library_dependencies[source_library].add(target_library)
    try:
        order = dependency_first_order(relevant, dependencies)
        library_order = dependency_first_order(set(library_dependencies), library_dependencies)
    except ValueError as exc:
        issues.append(str(exc))
        order, library_order = [], []
    return order, {key: sorted(value) for key, value in library_dependencies.items()}, library_order, sorted(set(issues))
