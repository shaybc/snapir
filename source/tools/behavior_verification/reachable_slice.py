"""Validate graph provenance and references before exposing a parser-produced slice."""

from collections import defaultdict
from models.unit_reachable_slice import UnitReachableSlice
from models.reachable_code_node import ReachableCodeNode
from models.reachable_call_edge import ReachableCallEdge


def _provenance(attributes, excerpt, sources):
    identity = attributes.get('source_identity')
    source = sources.get(identity)
    if source is None or attributes.get('source_hash') != source['content_hash'] or not excerpt.strip() or excerpt not in source['content']:
        raise ValueError('Reachability evidence is outside its supplied source revision')
    start, end = int(attributes['start_line']), int(attributes['end_line'])
    lines = source['content'].splitlines(keepends=True)
    if start < 1 or end < start or end > len(lines) or excerpt not in ''.join(lines[start - 1:end]):
        raise ValueError('Reachability source lines do not contain the reported excerpt')


def read_reachable_slice(element, boundary, sources, paths):
    """Reject fabricated excerpts and dangling graph IDs without weakening boundary discovery."""
    result = UnitReachableSlice(source_manifest_hash=boundary.source_manifest_hash,
                               configuration_hash=boundary.configuration_hash)
    if element is None:
        result.issues.append('Java analysis returned no reachability graph')
        return result
    try:
        result = UnitReachableSlice(status=element.get('status'), source_manifest_hash=boundary.source_manifest_hash,
                                   configuration_hash=boundary.configuration_hash)
        if element.get('candidate_universe') != result.candidate_universe:
            raise ValueError('Unexpected reachability candidate universe')
        nodes, edges = {}, {}
        for item in element.findall('code'):
            excerpt = item.findtext('excerpt', '')
            _provenance(item.attrib, excerpt, sources)
            node = ReachableCodeNode(**item.attrib, excerpt=excerpt,
                source_file=paths.get(item.get('source_identity')))
            if node.id in nodes:
                raise ValueError('Duplicate reachable code identity')
            nodes[node.id] = node
        external = sorted({item.get('id') for item in element.findall('external')})
        if any(not identity or not identity.startswith('external:') for identity in external):
            raise ValueError('Invalid external call identity')
        permitted = set(nodes) | set(external)
        roots = defaultdict(list)
        for item in element.findall('root'):
            if item.get('id') not in nodes:
                raise ValueError('Reachability root has no source node')
            roots[item.get('kind')].append(item.get('id'))
        for item in element.findall('edge'):
            excerpt = item.findtext('excerpt', '')
            if item.get('source_identity'):
                _provenance(item.attrib, excerpt, sources)
            edge = ReachableCallEdge(**item.attrib, excerpt=excerpt,
                candidates=[node.get('id') for node in item.findall('candidate')],
                source_file=paths.get(item.get('source_identity')))
            if edge.id in edges or edge.from_id and edge.from_id not in nodes or not set(edge.candidates) <= permitted:
                raise ValueError('Reachability edge contains duplicate or unavailable identities')
            if not edge.from_id and (edge.kind not in {'configured_construction', 'configured_initialization', 'configured_property_binding', 'receiver_construction'} or edge.source_identity):
                raise ValueError('Unattributed reachability edge is not configured setup')
            edges[edge.id] = edge
        result.nodes = [nodes[key] for key in sorted(nodes)]
        result.edges = [edges[key] for key in sorted(edges)]
        result.roots = {key: sorted(set(values)) for key, values in sorted(roots.items())}
        result.external_signatures = external
        result.issues = [item.get('message') for item in element.findall('issue')]
        # Certainty describes a statically resolved path, never guaranteed execution.
        certain = set(result.roots.get('entry', []))
        for edge in result.edges:
            if not edge.from_id and edge.kind.startswith('configured_') and not edge.uncertain and not edge.unbounded:
                certain.update(set(edge.candidates) & set(nodes))
        changed = True
        while changed:
            before = len(certain)
            for edge in result.edges:
                if edge.from_id in certain and not edge.uncertain and not edge.unbounded:
                    certain.update(set(edge.candidates) & set(nodes))
            changed = len(certain) != before
        for node in result.nodes:
            node.path_certainty = 'certain' if node.id in certain else 'uncertain'
        if result.issues or any(edge.unbounded for edge in result.edges):
            result.status = 'verification_incomplete'
        if not result.roots.get('entry'):
            result.status = 'verification_incomplete'
            result.issues.append('Reachability has no original entry root')
    except (ValueError, TypeError, KeyError) as exc:
        result = UnitReachableSlice(status='verification_incomplete', source_manifest_hash=boundary.source_manifest_hash,
                                   configuration_hash=boundary.configuration_hash, issues=[str(exc)])
    return result
