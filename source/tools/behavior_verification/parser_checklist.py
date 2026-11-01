"""Validate parser-produced checklist provenance before publishing the static inventory."""

import base64
import hashlib
from models.parser_checklist_item import ParserChecklistItem
from models.unit_parser_checklist import UnitParserChecklist
from tools.behavior_verification.reachable_slice import _provenance


def read_parser_checklist(element, boundary, sources, paths):
    """Reject unavailable source, duplicate identities and references outside the slice."""
    result = UnitParserChecklist(source_manifest_hash=boundary.source_manifest_hash,
                                 configuration_hash=boundary.configuration_hash)
    graph = boundary.reachable_slice
    if graph is None or not graph.nodes:
        result.status = 'verification_incomplete'
        result.issues.append('Parser checklist has no validated reachable source graph')
        return result
    result.reachability_status = graph.status
    if element is None:
        result.status = 'verification_incomplete'
        result.issues.append('Java analysis returned no parser checklist')
        return result
    try:
        if element.get('schema_version') != result.schema_version:
            raise ValueError('Unexpected parser checklist schema')
        status = element.get('status')
        if status not in {'extracted', 'verification_incomplete'}:
            raise ValueError('Unexpected parser checklist status')
        nodes = {node.id: node for node in graph.nodes}
        permitted = set(nodes) | set(graph.external_signatures)
        items = {}
        for item in element.findall('item'):
            excerpt = item.findtext('excerpt', '')
            _provenance(item.attrib, excerpt, sources)
            owner = nodes.get(item.get('code_node_id'))
            if owner is None or owner.source_identity != item.get('source_identity') or owner.source_hash != item.get('source_hash'):
                raise ValueError('Parser checklist item is outside its reachable source body')
            start = int(item.get('start_line')), int(item.get('start_column'))
            end = int(item.get('end_line')), int(item.get('end_column'))
            if start < (owner.start_line, owner.start_column) or end > (owner.end_line, owner.end_column) or end < start:
                raise ValueError('Parser checklist source range exceeds its reachable body')
            properties = {}
            for value in item.findall('property'):
                name = value.get('name')
                if not name or name in properties or value.get('encoding') != 'utf-16be-base64':
                    raise ValueError('Invalid or duplicate parser checklist property')
                properties[name] = base64.b64decode(value.text or '', validate=True).decode('utf-16-be', errors='surrogatepass')
            parsed = ParserChecklistItem(**item.attrib, excerpt=excerpt, properties=properties,
                arguments=[value.text or '' for value in item.findall('argument')],
                candidates=[value.get('id') for value in item.findall('candidate')],
                path_certainty=owner.path_certainty, source_file=paths.get(owner.source_identity))
            span = ':'.join(map(str, (*start, *end)))
            identity = '\0'.join((owner.id, parsed.kind, parsed.detail, span))
            expected_id = 'check-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
            if parsed.id != expected_id or parsed.id in items or not set(parsed.candidates) <= permitted:
                raise ValueError('Parser checklist has duplicate IDs or unavailable candidates')
            items[parsed.id] = parsed
        result.items = [items[key] for key in sorted(items)]
        result.issues = [item.get('message', '') for item in element.findall('issue')]
        result.status = 'verification_incomplete' if result.issues else status
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        result.status = 'verification_incomplete'
        result.items = []
        result.issues = [str(exc)]
    return result
