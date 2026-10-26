"""Resolve context ancestry and field evidence within one consuming operation context."""

from tools.conversion_tools.context_field_resolver_tool import _infer_java_type, _context_fields
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.conversion_tools.scoped_closure.collection_policy import effective_children, INDEXED_WRAPPERS


def resolve_contexts(access, context, sources, operation, issue):
    """Follow qualified parent bindings, blocking missing parents and repeated identities."""
    chain, seen = [], set()
    name = operation.get('operationContext', '')
    if not name:
        issue(context.operation_id, 'Operation context is not evidenced')
    while name and name.lower() not in ('nil', 'none', 'null'):
        try:
            reference = access.resource(context, 'contexts:' + name)
            if reference.kind != 'context':
                raise ValueError('Selected context binding has the wrong entity kind')
            if reference.definition_id in seen:
                issue(reference.definition_id, 'Context parent cycle')
                break
            seen.add(reference.definition_id)
            element = sources.xml(reference)
            chain.append(dict(definition_id=reference.definition_id, entity_id=reference.entity_id,
                              note=reference.note, attributes=dict(element.attrib),
                              declared_fields=[dict(tag=child.tag, attributes=dict(child.attrib))
                                               for child in effective_children(element, lambda node: False)]))
            name = element.get('parent', '')
        except (ValueError, OSError) as exc:
            issue(name, str(exc))
            break
    return chain


def resolve_fields(chain, formats, java_origins):
    """Retain qualified field provenance; literal Java access is static evidence, not exhaustive."""
    fields = {}

    def add(name, level, source, writer=None, reader=None, tag=''):
        if not name:
            return
        field = fields.setdefault(name, dict(name=name, context_definition_id=level,
            source=source, inferred_type='List<Object>' if tag in INDEXED_WRAPPERS else _infer_java_type(tag),
            written_by=[], read_by=[],
            inherited=bool(chain and level != chain[0]['definition_id'])))
        if writer and writer not in field['written_by']:
            field['written_by'].append(writer)
        if reader and reader not in field['read_by']:
            field['read_by'].append(reader)

    for level in chain:
        for child in level['declared_fields']:
            attributes = child['attributes']
            name = attributes.get('id') or attributes.get('dataName') or attributes.get('name')
            add(name, level['definition_id'], 'context', tag=child['tag'])
    primary = chain[0]['definition_id'] if chain else ''

    def visit(node):
        add(node.attributes.get('dataName'), primary, 'formatter', writer=node.occurrence_id, tag=node.tag)
        for child in node.children:
            visit(child)

    for node in formats.values():
        visit(node)
    for origin in java_origins:
        if origin.get('status') != 'verified_source':
            continue
        source = read_java_source(origin['source_file'], expected_hash=origin['source_hash'])
        for name in _context_fields(source, ('setValueAt', 'setValue')):
            add(name, primary, 'implclass', writer=origin['definition_id'])
        for name in _context_fields(source, ('getValueAt', 'getValue')):
            add(name, primary, 'implclass', reader=origin['definition_id'])
    return list(fields.values())
