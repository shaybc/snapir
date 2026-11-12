"""Select verified application obligations behind an inherited OP-step execution entry."""


def step_entry_evidence(boundary, sources, component_id, origin, *, collect_checklists=True):
    """Return reachable method signatures and parser items from this step's supplied sources.

    Uses existing analyzer roots/edges, including conservative framework roots, without
    resolving class hierarchies or interpreting framework behavior. Pure selection;
    raises ValueError for unresolved entries or conflicting application provenance.
    The legacy invocation stays in the boundary record; selected methods are business
    test obligations, not a replacement public invocation API.
    """
    if boundary.get('analysis_status') != 'identified':
        reason = '; '.join(boundary.get('issues', [])) or 'No resolved execution entry was recorded'
        raise ValueError('OP-step entry resolution failed: ' + str(boundary.get('implementation_class')) + ': ' + reason)
    identities = {origin.get('definition_id')}
    identities.update(item['definition_id'] for item in origin.get('supporting_sources', []))
    supplied = {source['identity']: source['content_hash'] for source in sources
                if source.get('component_id') == component_id or source['identity'] in identities}
    legacy = boundary.get('legacy_method')
    if legacy and supplied.get(legacy['source_identity']) != legacy['source_hash']:
        raise ValueError('Resolved OP-step entry source is not supplied at its recorded revision: ' + legacy['signature'])
    graph = boundary.get('reachable_slice') or {}
    pending = [identity for roots in graph.get('roots', {}).values() for identity in roots]
    edges = {}
    for edge in graph.get('edges', []):
        if not edge['from_id']:
            pending.extend(edge.get('candidates', []))
        else:
            edges.setdefault(edge['from_id'], []).extend(edge.get('candidates', []))
    reached = set()
    while pending:
        identity = pending.pop()
        if identity in reached: continue
        reached.add(identity)
        pending.extend(edges.get(identity, []))
    selected = {}
    for node in graph.get('nodes', []):
        if node['id'] not in reached or node['source_identity'] not in supplied: continue
        if supplied[node['source_identity']] != node['source_hash']:
            raise ValueError('OP-step reachable source revision changed: ' + node['signature'])
        selected[node['id']] = node
    methods = {node['signature'] for node in selected.values() if node['kind'] == 'method'}
    if legacy and legacy['signature'] not in methods:
        raise ValueError('Resolved OP-step entry has no reachable source evidence: ' + legacy['signature'])
    items = []
    for item in (boundary.get('parser_checklist') or {}).get('items', []) if collect_checklists else []:
        node = selected.get(item['code_node_id'])
        if node is None: continue
        if (item['source_identity'], item['source_hash']) != (node['source_identity'], node['source_hash']):
            raise ValueError('Conflicting inherited OP-step parser provenance: ' + item['id'])
        items.append(item)
    return methods, items
