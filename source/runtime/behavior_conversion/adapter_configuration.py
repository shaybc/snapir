"""Resolve exact configured evidence for adapter preparation without changing model candidates."""
from copy import deepcopy
from runtime.component_conversion.scope import trusted_partition_configuration
from tools.conversion_tools.component_partition import subtree_at, parent_configuration, partition_identity
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def resolve_configuration(payload):
    """Return a detached unit and partition context; reject missing or conflicting evidence."""
    partition = payload.get('format_partition')
    if partition is None:
        unit = deepcopy(payload.get('configured_format') or payload.get('configured_unit') or payload.get('unit') or payload)
        if 'effective_configuration' not in unit:
            raise ValueError('Configured boundary XML evidence is required for adapter repair')
        return unit, None
    original = trusted_partition_configuration(payload)
    unit = deepcopy(original['configured_format'])
    tree = unit['effective_configuration']
    selector = partition.get('selector')
    if not isinstance(selector, list) or any(type(index) is not int or index < 0 for index in selector):
        raise ValueError('Adapter partition selector is invalid')
    try:
        selected = subtree_at(tree, selector)
    except (IndexError, KeyError, TypeError) as error:
        raise ValueError('Adapter partition selector does not resolve') from error
    expected_identity = partition_identity(original['group_id'], tree, selector) if selector else original['group_id']
    if (payload.get('group_id') != expected_identity or partition.get('parent_group') != original['group_id']
            or partition.get('direction') != unit['kind'] or partition.get('configuration_hash') != digest(selected)
            or partition.get('parents') != parent_configuration(tree, selector)
            or partition.get('referenced_definitions') != unit['referenced_definitions']):
        raise ValueError('Adapter partition configuration identity or hash changed')
    unit['effective_configuration'] = deepcopy(selected)
    if selector:
        # Whole-format XML must never masquerade as the selected child configuration.
        unit.pop('configuration_xml', None)
    return unit, deepcopy(partition)
