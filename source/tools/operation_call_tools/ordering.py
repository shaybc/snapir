"""Calculate dependency-first waves with explicit strongly connected groups."""

import heapq
import hashlib


def operation_waves(graph):
    """Return deterministic SCC groups and waves without recursion limits on large vaults."""
    edges = {key: set() for key in graph['operations']}
    reverse = {key: set() for key in edges}
    for call in graph['calls']:
        edges[call['caller']].add(call['callee'])
        reverse[call['callee']].add(call['caller'])
    seen, finished = set(), []
    for start in sorted(edges):
        if start in seen:
            continue
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                finished.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend((other, False) for other in sorted(edges[node], reverse=True) if other not in seen)
    groups, assigned = [], {}
    for start in reversed(finished):
        if start in assigned:
            continue
        group, pending = [], [start]
        index = len(groups)
        assigned[start] = index
        while pending:
            node = pending.pop()
            group.append(node)
            for other in reverse[node]:
                if other not in assigned:
                    assigned[other] = index
                    pending.append(other)
        groups.append(sorted(group))
    dependencies = {i: {assigned[target] for node in nodes for target in edges[node] if assigned[target] != i}
                    for i, nodes in enumerate(groups)}
    dependents = {i: set() for i in dependencies}
    for i, targets in dependencies.items():
        for target in targets:
            dependents[target].add(i)
    remaining = {i: len(targets) for i, targets in dependencies.items()}
    ready = [(groups[i][0], i) for i, count in remaining.items() if not count]
    heapq.heapify(ready)
    waves = {}
    while ready:
        _, i = heapq.heappop(ready)
        waves[i] = 1 + max((waves[target] for target in dependencies[i]), default=0)
        for parent in dependents[i]:
            remaining[parent] -= 1
            if remaining[parent] == 0:
                heapq.heappush(ready, (groups[parent][0], parent))
    # Unresolved calls must never make an incomplete chain look ready.
    blocked = {issue['operation'] for issue in graph['issues'] if issue['operation'] in edges}
    cyclic = {node for nodes in groups for node in nodes if len(nodes) > 1 or node in edges[node]}
    cycle_ids = {i: 'cycle-' + hashlib.sha256('\n'.join(nodes).encode()).hexdigest()[:12]
                 for i, nodes in enumerate(groups) if any(node in cyclic for node in nodes)}
    pending = list(blocked)
    while pending:
        for parent in reverse[pending.pop()]:
            if parent not in blocked:
                blocked.add(parent)
                pending.append(parent)
    return {node: dict(wave=None if node in blocked else waves[assigned[node]],
        cycle_group=cycle_ids.get(assigned[node], ''),
        prerequisites=sorted(edges[node]), calls_count=len(edges[node]), callers_count=len(reverse[node]),
        issue='Unresolved dependency' if node in blocked else 'Cycle requires coordinated contracts' if node in cyclic else '')
        for node in sorted(edges)}


def ordered_operations(graph, selected, available=()):
    """Order selected operations; reject unresolved targets, cycles and omitted prerequisites."""
    waves = operation_waves(graph)
    selected = set(selected)
    for node in sorted(selected):
        if node not in waves:
            raise ValueError('Operation is missing from mapped call graph: ' + node)
        item = waves[node]
        if item['issue']:
            raise ValueError(node + ': ' + item['issue'])
        missing = set(item['prerequisites']) - selected - set(available)
        if missing:
            raise ValueError(node + ': include prerequisite operations: ' + ', '.join(sorted(missing)))
    return sorted(selected, key=lambda node: (waves[node]['wave'], node))
