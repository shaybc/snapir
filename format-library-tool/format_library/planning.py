"""Dependency-first conversion groups from recorded class relations."""
from format_library.files import digest


def build_plan(discovery):
    """Group cycles; retain full original source closures and explicit blocker evidence."""
    classes = discovery['classes']
    targets = {name for name, item in classes.items() if item['kind'] in {'format', 'decorator'}
               and not item['abstract'] and not item['framework']}
    projects = {item['id']: item for item in discovery.get('projects', [])}
    closures, dependencies, blockers = {}, {}, {}
    for name in sorted(targets):
        seen, pending, problems = set(), [name], list(discovery.get('issues', []))
        while pending:
            current = pending.pop()
            if current in seen or current not in classes:
                continue
            seen.add(current)
            item = classes[current]
            problems.extend(current + ': ' + issue for issue in item.get('issues', []))
            problems.extend(projects.get(item['project'], {}).get('issues', []))
            pending.extend(item['dependencies'])
        closures[name] = sorted(seen)
        dependencies[name] = sorted((seen & targets) - {name})
        blockers[name] = sorted(set(problems))
    # Tarjan SCCs keep actual code cycles in one coordinated conversion folder.
    serial, low, stack, active, groups = {}, {}, [], set(), []
    def visit(name):
        serial[name] = low[name] = len(serial)
        stack.append(name); active.add(name)
        for target in dependencies[name]:
            if target not in serial:
                visit(target); low[name] = min(low[name], low[target])
            elif target in active:
                low[name] = min(low[name], serial[target])
        if low[name] == serial[name]:
            members = []
            while True:
                member = stack.pop(); active.remove(member); members.append(member)
                if member == name:
                    break
            groups.append(sorted(members))
    for name in sorted(targets):
        if name not in serial:
            visit(name)
    owners = {name: 'group-' + digest(members)[:16] for members in groups for name in members}
    result = {}
    for members in groups:
        identity = owners[members[0]]
        prerequisites = sorted({owners[target] for member in members for target in dependencies[member]
                                if owners[target] != identity})
        result[identity] = dict(id=identity, members=members, dependencies=prerequisites,
            source_classes=sorted({target for member in members for target in closures[member]}),
            blockers=sorted({issue for member in members for issue in blockers[member]}))
    pending, ordered = set(result), []
    while pending:
        ready = sorted(key for key in pending if not (set(result[key]['dependencies']) & pending))
        if not ready:
            raise ValueError('Internal error: dependency groups still contain a cycle')
        for key in ready:
            result[key]['order'] = len(ordered) + 1
            ordered.append(result[key]); pending.remove(key)
    return dict(schema_version='format-library-plan-v1', discovery_hash=digest(discovery),
                groups=ordered, classes=classes, hashes=discovery['hashes'], projects=discovery['projects'],
                issues=discovery.get('issues', []))


def select_groups(plan, names):
    """Include selected groups and their prerequisites; require exact names or unique short names."""
    groups = {item['id']: item for item in plan['groups']}
    selected = set()
    if not names:
        return list(groups.values())
    for name in names:
        matches = [key for key, item in groups.items() if key == name or any(
            member == name or member.rsplit('.', 1)[-1] == name for member in item['members'])]
        if len(matches) != 1:
            raise ValueError('Component selection is missing or ambiguous: ' + name)
        selected.add(matches[0])
    pending = list(selected)
    while pending:
        for key in groups[pending.pop()]['dependencies']:
            if key not in selected:
                selected.add(key); pending.append(key)
    return [item for item in plan['groups'] if item['id'] in selected]
