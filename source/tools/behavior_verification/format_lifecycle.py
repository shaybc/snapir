"""Prepare independent basic-format boundaries and validate returned lifecycle provenance."""
from copy import deepcopy
from models.format_lifecycle import FormatLifecycle
from tools.behavior_verification.boundary_contracts import digest


def basic_identity(unit_id, implementation):
    """Bind basic discovery to the configured consumer and exact implementing class."""
    return 'basic-format-' + digest([unit_id, implementation])


def expanded_preparation(preparation):
    """Add undecorated basic roots without depending on whole-format reachability success."""
    result = dict(preparation, operations={})
    basic = set()
    for operation, item in preparation.get('operations', {}).items():
        units = list(item.get('units', []))
        extra = {}
        for unit in units:
            if unit['kind'] not in {'request_unformat', 'response_format'} or unit.get('format_scope') == 'basic':
                continue
            def visit(node):
                name = node.get('java_class')
                if name:
                    identity = basic_identity(unit['unit_id'], name)
                    clone = deepcopy(unit)
                    clone.update(unit_id=identity, format_scope='basic', referenced_definitions=[], configuration_xml='',
                                 effective_configuration=dict(java_class=name, attributes=deepcopy(node.get('attributes', {}))))
                    extra.setdefault(identity, clone)
                for child in node.get('children', []): visit(child)
            visit(unit['effective_configuration'])
            for definition in unit.get('referenced_definitions', []): visit(definition)
        basic.update(extra)
        result['operations'][operation] = dict(item, units=units + list(extra.values()))
    return result, basic


def read_lifecycle(element, sources):
    """Reject lifecycle metadata outside the supplied source revision."""
    if element is None:
        return None
    invocations = []
    for invocation in element.findall('invocation'):
        value = dict(invocation.attrib, parameters=[node.get('type') for node in invocation.findall('parameter')])
        source = sources.get(value['source_identity'])
        if source is None or source['content_hash'] != value['source_hash']:
            raise ValueError('Format lifecycle is outside its supplied source revision')
        invocations.append(value)
    ordering = [dict(node.attrib) for node in element.findall('ordering')]
    for proof in ordering:
        source = sources.get(proof['source_identity'])
        if source is None or source['content_hash'] != proof['source_hash'] or not (1 <= int(proof['start_line']) <= int(proof['end_line']) <= len(source['content'].splitlines())):
            raise ValueError('Format lifecycle ordering is outside its supplied source revision')
    if len(invocations) > 1 and not ordering:
        raise ValueError('Format lifecycle sequence has no source ordering evidence')
    return FormatLifecycle(**element.attrib, invocations=invocations, ordering_evidence=ordering)
