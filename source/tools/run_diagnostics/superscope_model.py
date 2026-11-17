"""Build four navigation levels from converter facts, retaining canonical references and cycles."""
from collections import deque
import json
from pathlib import Path

from tools.conversion_tools.scoped_reuse.fingerprints import digest

MAX_OBJECTS = 20000


def focus_identity(graph, selected):
    """Accept a stable recorded ID or a unique exact class/operation label."""
    if selected in graph.nodes:
        return selected
    candidates = [key for key, node in graph.nodes.items() if node['label'] == selected]
    if len(candidates) != 1:
        raise ValueError('Select an exact recorded node ID; the label is absent or ambiguous: ' + str(selected))
    return candidates[0]


def build_model(graph, focus):
    """Use aliases only for navigation; parent grouping never asserts source containment."""
    adjacency = {key: set() for key in graph.nodes}
    inheritance = {key: set() for key in graph.nodes}
    for edge in graph.edges:
        adjacency[edge['from']].add(edge['to'])
        if edge['relation'] in {'extends', 'implements'}:
            inheritance[edge['from']].add(edge['to'])
    def closure(initial, edges):
        seen, pending = set(), deque(initial)
        while pending:
            key = pending.popleft()
            if key in seen:
                continue
            seen.add(key)
            pending.extend(sorted(edges[key] - seen))
        return seen
    objects, connections, views, mapping = [], {}, [], {}
    tags = set()
    def emit(key, parent, level, ancestors):
        if len(objects) >= MAX_OBJECTS:
            raise ValueError('Selected graph exceeds 20000 display objects; choose a more focused component. No partial model was exported.')
        identity = 'object-' + digest([parent, key])[:24]
        record = graph.nodes[key]
        status = record.get('status', 'not_recorded')
        selected_tags = {status, record.get('decision', 'not_recorded')}
        entries = record.get('entry_points', [])
        selected_tags.update('entry-' + str(entry.get('direction') or 'not_recorded') for entry in entries if entry.get('role') == 'declares')
        tags.update(selected_tags)
        description = status + (' — ' + str(record['reason']) if record.get('reason') else '')
        signatures = ['[' + entry.get('direction', '?') + '] ' + entry.get('signature', entry.get('expected_signature', 'not recorded'))
                      + ' (' + entry.get('role', 'selected') + '; ' + entry.get('status', 'not_recorded') + ')' for entry in entries]
        declared = [entry for entry in entries if entry.get('role') == 'declares']
        if declared:
            description += '\n' + '\n'.join('[' + entry['direction'] + '] ' + entry['signature'] for entry in declared)
        item = dict(id=identity, type='system' if level == 1 else 'app' if level == 2 else 'component',
            name=record['label'] + (' [entry: ' + ', '.join(sorted({entry['direction'] for entry in declared})) + ']' if declared else ''),
            description=description, tags=sorted('fact-' + digest(tag)[:16] for tag in selected_tags),
            details='Canonical converter node: ' + key + '\nNavigation level: ' + str(level) +
                '\nDisplay grouping is navigation only; labelled arrows describe actual relationships.\n' +
                '\n'.join(signatures) + '\nRecorded evidence:\n' + json.dumps(record, indent=2))
        if parent:
            item['parent'] = parent
        source = record.get('source_file')
        if source and Path(source).is_absolute():
            item['links'] = [dict(name='Original source', url=Path(source).as_uri())]
        objects.append(item)
        mapping[identity] = dict(canonical_id=key, level=level, reference=key in ancestors)
        return identity
    def expand(key, parent, level, ancestors):
        current = emit(key, parent, level, ancestors)
        visible = {key: current, **ancestors}
        direct = adjacency[key] | closure(inheritance[key], inheritance)
        # At the last container, flatten every remaining descendant, rather than discard a fifth level.
        children = closure(direct, adjacency) if level == 3 else direct
        child_aliases = {}
        for target in sorted(children - set(visible)):
            if level < 3:
                child_aliases[target] = expand(target, current, level + 1, {**ancestors, key: current})
            else:
                child_aliases[target] = emit(target, current, 4, {**ancestors, key: current})
        visible.update(child_aliases)
        local_edges = []
        for edge in graph.edges:
            if edge['from'] not in visible or edge['to'] not in visible:
                continue
            source, target = visible[edge['from']], visible[edge['to']]
            identity = 'connection-' + digest([edge['id'], source, target])[:24]
            connections[identity] = dict(id=identity, **{'from': source, 'to': target},
                description=edge['relation'].replace('_', ' '), details=json.dumps(edge, indent=2))
            local_edges.append(identity)
        views.append(dict(id='focus-' + current, name=graph.nodes[key]['label'],
            objects=list(dict.fromkeys([current, *child_aliases.values(), *ancestors.values()])), connections=local_edges))
        return current
    root = expand(focus, None, 1, {})
    def color(tag):
        if tag.startswith('entry-'):
            return '#1d4ed8'
        if tag in {'component_validated', 'build_and_tests_passed'}:
            return '#15803d'
        if tag in {'incomplete', 'failed', 'unresolved', 'unbounded', 'not_run'}:
            return '#b91c1c'
        return '#6d28d9' if tag == 'framework_boundary' else '#64748b'
    model = dict(version=1, name='Conversion: ' + graph.nodes[focus]['label'], objects=objects,
        connections=list(connections.values()), tagGroups=[dict(id='conversion', name='Recorded conversion facts',
            tags=[dict(id='fact-' + digest(tag)[:16], name=tag.replace('_', ' '), color=color(tag)) for tag in sorted(tags)])])
    return model, views, mapping, dict(diagram='focus-' + root, object=root, focus=True)
