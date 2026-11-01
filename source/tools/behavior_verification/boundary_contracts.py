"""Derive comparison entry points from configured units, never from AI-generated facts."""

import hashlib
import json

from models.unit_verification_boundary import UnitVerificationBoundary


CONTROLS = ['clock', 'random_seed', 'initial_settings', 'external_responses']

CONTRACTS = {
    'request_unformat': dict(method_name='unformat', parameter_contract=['java.lang.String', 'Context'],
        return_contract='void', inputs=['request_xml', 'initial_context', 'initialization', *CONTROLS]),
    'response_format': dict(method_name='format', parameter_contract=['Context'],
        return_contract='java.lang.String', inputs=['initial_context', 'initialization', *CONTROLS]),
    'configured_step': dict(method_name='execute', parameter_contract=[], return_contract='int',
        inputs=['initial_context', 'initialization', *CONTROLS]),
}


def digest(value):
    """Bind comparison metadata to exact source text and effective configuration."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _classes(node):
    if node.get('java_class'):
        yield node['java_class']
    for decorator in node.get('decorators', []):
        if decorator.get('java_class'):
            yield decorator['java_class']
    for child in node.get('children', []):
        yield from _classes(child)


def _bindings(node):
    for item in [node, *node.get('decorators', [])]:
        if item.get('java_class'):
            yield dict(implementation_class=item['java_class'], occurrence_id=item.get('occurrence_id'),
                source_selector=item.get('source_selector'), attributes=item.get('attributes', {}))
    for child in node.get('children', []):
        yield from _bindings(child)


def _format_entry(unit):
    node = unit['effective_configuration']
    definitions = {item['definition_id']: item for item in unit.get('referenced_definitions', [])}
    visited = set()
    while not node.get('java_class'):
        identity = node.get('reference_definition_id')
        if identity:
            if identity in visited or identity not in definitions:
                raise ValueError('Format entry reference is cyclic or unavailable: ' + identity)
            visited.add(identity)
            node = definitions[identity]
        elif node.get('tag') == 'fmtDef' and len(node.get('children', [])) == 1:
            node = node['children'][0]
        else:
            raise ValueError('Format entry requires exactly one configured implementing body')
    return node['java_class']


def boundary_contract(unit, mappings=None):
    """Describe the original boundary, including all result channels for every unit kind."""
    contract = CONTRACTS[unit['kind']]
    configuration = unit['effective_configuration']
    sources = [dict(identity=item['identity'], source_hash=item['content_hash'],
                    analysis_content_hash=hashlib.sha256(item['content'].encode('utf-8')).hexdigest())
               for item in unit['sources']]
    boundary = UnitVerificationBoundary(unit_id=unit['unit_id'], unit_fingerprint=unit['fingerprint'],
        operation_identity=unit['operation_identity'], kind=unit['kind'], **contract,
        observable_results=['return_value', 'context_writes', 'context_removals', 'exceptions', 'external_calls'],
        configuration_hash=digest(dict(effective=configuration, xml=unit['configuration_xml'],
                                      referenced_definitions=unit.get('referenced_definitions', []))),
        source_manifest_hash=digest(sorted(sources, key=lambda item: item['identity'])))
    try:
        if unit['kind'] == 'configured_step':
            implementation = configuration['attributes'].get('implClass') or (mappings or {}).get('opStep')
            if not implementation:
                raise ValueError('Configured step has no evidenced implementation binding')
            roots = [implementation]
            bindings = [dict(implementation_class=implementation, occurrence_id=unit.get('occurrence_id'),
                             attributes=configuration['attributes'])]
        else:
            implementation = _format_entry(unit)
            roots = [*_classes(configuration), *(name for node in unit.get('referenced_definitions', [])
                                                for name in _classes(node))]
            bindings = [*_bindings(configuration), *(item for node in unit.get('referenced_definitions', []) for item in _bindings(node))]
        boundary.implementation_class = implementation
        boundary.setup_class_roots = sorted(set(roots))
        from models.configured_setup_binding import ConfiguredSetupBinding
        boundary.setup_bindings = [ConfiguredSetupBinding(**item) for item in bindings]
    except (KeyError, ValueError) as exc:
        boundary.issues.append(str(exc))
    return boundary
