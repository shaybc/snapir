"""Project bounded subtree work while keeping complete original evidence on the trusted side."""
from copy import deepcopy
from models.native_component_bundle import NativeComponentBundle
from models.native_format_component_bundle import NativeFormatComponentBundle
from tools.conversion_tools.component_partition import partition_tree, parent_configuration, partition_identity, subtree_at
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.response_json import JSON_INSTRUCTION

PART_INSTRUCTION = '''
Return NativeComponentBundle for only format_partition.tree, using its assigned native package.
This is a configured subtree, not a complete format. Keep parent-derived state, namespaces,
prefix ownership, decorator order, collection order, exceptions and evaluation/callback order
explicit in runtime_inputs and observable_effects. Include a runtime_inputs entry named
parent_environment describing the actual typed parent inputs/collaborators (or why none are read).
Never precompute children or reorder effects. Invoke supplied frozen child APIs at their original
positions. Do not implement a Composer interpreter. Keep the supplied original source entry points
and exact original dependency IDs, with specialized configuration. Cite every supplied parser
item in actual production source, including prerequisites; citations are not behavioral proof.
Whole-format parser and original/native comparison remain mandatory after composition.
'''


def partition_request(original, tree, selector, children):
    """Retain full source/checklist; remove only replaced configuration and native source duplication."""
    request = deepcopy(original)
    identity = partition_identity(original['group_id'], tree, selector)
    request['format_partition'] = dict(version='configured-subtree-v1', parent_group=original['group_id'],
        selector=list(selector), configuration_hash=digest(subtree_at(tree, selector)),
        tree=partition_tree(tree, selector, children), parents=parent_configuration(tree, selector),
        direction=original['configured_format']['kind'])
    request['format_partition']['referenced_definitions'] = deepcopy(original['configured_format']['referenced_definitions'])
    request.pop('configured_format')
    # Whole original XML/tree stay in the trusted validator. They are not an AI summary.
    for node in request['components'].values():
        node['configuration'] = dict(partition=identity)
    request['group_id'] = identity if selector else original['group_id']
    request['kind'] = 'format_subtree' if selector else 'format_composition'
    request['native_package'] = original['native_package'] + '.p' + digest(list(selector))[:12] if selector else original['native_package']
    for dependency in request['prerequisite_components']:
        dependency.pop('sources', None)
    request['prerequisite_components'].extend(children[path] for path in sorted(children)
        if path[:-1] == tuple(selector))
    if not selector:
        request['configured_format'] = {key: value for key, value in original['configured_format'].items()
            if key not in {'effective_configuration', 'configuration_xml', 'referenced_definitions'}}
    else:
        request.pop('verification_boundary', None)
    return request


def fits_partition(request, instruction, profile):
    """Measure the real schema, manual context and generation metadata before choosing a cut."""
    from runtime.behavior_conversion.compatibility import versioned_requirements
    schema = NativeFormatComponentBundle if request['kind'] == 'format_composition' else NativeComponentBundle
    payload = dict(request, schema=schema.model_json_schema(),
        versioned_requirements=versioned_requirements(profile, 'component_generation', request))
    try:
        encode_request(payload, instruction + '\n' + JSON_INSTRUCTION, profile.behavior_context_chars)
    except ValueError as exc:
        if 'exceeds its context budget' not in str(exc):
            raise
        return False
    return True
