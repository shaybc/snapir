"""Dependency-first conversion groups from recorded class relations."""
from format_library.files import digest
from format_library.foundation_planning import POLICY, foundation_selection, unowned_bases


def build_plan(discovery):
    """Group cycles; retain full original source closures and explicit blocker evidence."""
    classes, foundations, concrete, proposals = foundation_selection(discovery)
    targets = concrete | set(foundations)
    projects = {item['id']: item for item in discovery.get('projects', [])}
    closures, dependencies, blockers = {}, {}, {}
    for name in sorted(targets):
        scope = {}
        if 'dependency_scopes' in discovery:
            roots = [name] if name not in foundations else [
                other for other, label in foundations.items() if label == foundations[name]]
            for root in roots:
                for current, item in discovery['dependency_scopes'].get(root, {}).items():
                    combined = scope.setdefault(current, dict(item))
                    for field in ('dependencies', 'issues', 'required_members'):
                        combined[field] = sorted(set(combined.get(field, [])) | set(item.get(field, [])))
        seen, pending, problems = set(), [name], list(discovery.get('issues', []))
        while pending:
            current = pending.pop()
            if current in seen or current not in classes:
                continue
            seen.add(current)
            if current in foundations:
                pending.extend(other for other, label in foundations.items() if label == foundations[current])
            item = scope.get(current, classes[current])
            problems.extend(current + ': ' + issue for issue in item.get('issues', []))
            # Scoped resolution reports required missing symbols; project declarations remain diagnostics.
            if 'dependency_scopes' not in discovery:
                problems.extend(projects.get(item['project'], {}).get('issues', []))
            pending.extend(item['dependencies'])
        closures[name] = sorted(seen)
        dependencies[name] = sorted((seen & targets) - {name})
        blockers[name] = sorted(set(problems))
    required = {}
    for root, scope in discovery.get('dependency_scopes', {}).items():
        required[root] = {name: [*item.get('required_members', []),
            *('dynamic delegation: ' + call for call in item.get('dynamic_calls', []))]
            for name, item in scope.items()}
    # Explicit groups may intentionally collapse an original inheritance chain into one native base.
    for name, label in foundations.items():
        dependencies[name] = sorted(set(dependencies[name]) | {other for other, group in foundations.items()
                                                             if group == label and other != name})
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
    owners = {name: 'group-' + digest([POLICY, 'foundation' if any(member in foundations for member in members) else 'component', members])[:16]
              for members in groups for name in members}
    result = {}
    for members in groups:
        identity = owners[members[0]]
        prerequisites = sorted({owners[target] for member in members for target in dependencies[member]
                                if owners[target] != identity})
        stage = 'foundation' if any(member in foundations for member in members) else 'component'
        problems = sorted({issue for member in members for issue in blockers[member]})
        if stage == 'foundation' and any(member in concrete for member in members):
            problems.append('Foundation/concrete dependency cycle; review the selected foundation group boundary')
        missing_bases = unowned_bases(members, classes, proposals, foundations) if stage == 'component' else []
        if missing_bases:
            problems.append('Select shared ancestor foundations in foundation_groups: ' + ', '.join(missing_bases))
        result[identity] = dict(id=identity, members=members, stage=stage, policy=POLICY,
            name='+'.join(sorted({foundations[member] for member in members if member in foundations})) if stage == 'foundation' else members[0].rsplit('.', 1)[-1],
            dependencies=prerequisites,
            source_classes=sorted({target for member in members for target in closures[member]}),
            required_members={name: sorted({method for member in members for method in required.get(member, {}).get(name, [])})
                              for name in sorted({target for member in members for target in closures[member]})},
            blockers=problems)
    for item in result.values():
        if item['stage'] == 'foundation' and any(result[key]['stage'] != 'foundation' for key in item['dependencies']):
            item['blockers'].append('Foundation depends on a concrete formatter; revise explicit foundation groups')
    pending, ordered = set(result), []
    while pending:
        ready = sorted((key for key in pending if not (set(result[key]['dependencies']) & pending)),
                       key=lambda key: (result[key]['stage'] != 'foundation', key))
        if not ready:
            raise ValueError('Internal error: dependency groups still contain a cycle')
        if any(result[key]['stage'] == 'foundation' for key in ready):
            ready = [key for key in ready if result[key]['stage'] == 'foundation']
        for key in ready:
            result[key]['order'] = len(ordered) + 1
            ordered.append(result[key]); pending.remove(key)
    return dict(schema_version='format-library-plan-v2', policy=POLICY, foundation_candidates=proposals,
                foundation_settings=dict(groups=discovery.get('foundation_groups', {}),
                                         source_roots=discovery.get('foundation_source_roots', [])),
                discovery_hash=digest(discovery),
                groups=ordered, classes=classes, hashes=discovery['hashes'], projects=discovery['projects'],
                issues=discovery.get('issues', []),
                detailed_log=discovery.get('detailed_log'),
                unresolved_dependencies=discovery.get('unresolved_dependencies', []),
                dependency_policy=discovery.get('dependency_policy'))


def select_groups(plan, names, stage='all'):
    """Include selected groups and their prerequisites; require exact names or unique short names."""
    groups = {item['id']: item for item in plan['groups']}
    selected = set()
    if not names:
        selected = {key for key, item in groups.items() if stage == 'all' or item.get('stage') == stage}
    for name in names:
        matches = [key for key, item in groups.items() if (stage == 'all' or item.get('stage') == stage) and (key == name or item.get('name') == name or any(
            member == name or member.rsplit('.', 1)[-1] == name for member in item['members']))]
        if len(matches) != 1:
            raise ValueError('Component selection is missing or ambiguous: ' + name)
        selected.add(matches[0])
    pending = list(selected)
    while pending:
        for key in groups[pending.pop()]['dependencies']:
            if key not in selected:
                selected.add(key); pending.append(key)
    return [item for item in plan['groups'] if item['id'] in selected]
