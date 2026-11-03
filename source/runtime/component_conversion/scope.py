"""Authorize component requests only within fresh, explicitly selected scoped evidence."""
from contextlib import contextmanager
from contextvars import ContextVar
from tools.conversion_tools.component_identity import checked_plan, component_target, input_revision
from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints
from tools.behavior_verification.component_artifacts import verify_original_sources

_execution = ContextVar('basic_component_execution', default=None)
_partition_tasks = ContextVar('format_partition_tasks', default=None)


def trusted_partition_configuration(payload):
    """Return original configuration only for the active unchanged partition projection."""
    from copy import deepcopy
    partition = _partition_tasks.get()
    if not partition or payload.get('group_id') != partition[0] or payload.get('format_partition') != partition[1].get('format_partition'):
        raise ValueError('Adapter configuration requires the active trusted partition projection')
    original = partition[2]
    supplied = payload.get('configured_format', {})
    if any(value != original['configured_format'].get(key) for key, value in supplied.items()):
        raise ValueError('Adapter configuration changed the configured format identity')
    return deepcopy(original)


@contextmanager
def partition_task(identity, request, original):
    """Authorize one trusted subtree projection under its unchanged whole-format task."""
    from copy import deepcopy
    token = _partition_tasks.set((identity, deepcopy(request), deepcopy(original)))
    try:
        yield
    finally:
        _partition_tasks.reset(token)


@contextmanager
def component_execution(conn, config, profile, classpath, preparation, *, include_steps=False, include_formats=False):
    """Bind an explicit CF3 invocation; configured-unit generation remains gated separately."""
    if profile.scoped_native_mode != 'component_first_v1' or profile.conversion_strategy != 'behavior_units':
        raise ValueError('Basic components require the explicit component_first_v1 behavior mode')
    plan = checked_plan(preparation['component_plan'])
    selected = set(preparation['operations'])
    validate_checkpoints(conn, config, profile, classpath, selected)
    token = _execution.set(dict(conn=conn, config=config, profile=profile, classpath=classpath,
        selected=selected, plan=plan, target=component_target(profile), include_steps=include_steps, include_formats=include_formats,
        units={unit['unit_id']: unit for item in preparation['operations'].values() for unit in item.get('units', [])}))
    try:
        yield
    finally:
        _execution.reset(token)


def require_component_task(conn, config, profile, identity, payload=None):
    """Recheck checkpoint/source/target bindings before model calls and candidate publication."""
    partition = _partition_tasks.get()
    if partition and identity == partition[0] and payload is not None and payload.get('format_partition') is not None:
        if any(payload.get(key) != value for key, value in partition[1].items()):
            raise ValueError('Component request changed trusted subtree projection')
        return require_component_task(conn, config, profile, partition[2]['group_id'], partition[2])
    execution = _execution.get()
    if not execution or execution['conn'] is not conn or execution['config'] is not config or execution['profile'] is not profile:
        raise ValueError('Component generation is gated outside qualified component execution')
    group = next((item for item in execution['plan'].groups if item.group_id == identity), None)
    if group is None or group.wave is None:
        raise ValueError('Component group has unresolved prerequisites')
    from runtime.component_conversion.requests import basic_group
    from runtime.component_conversion.steps import step_group, source_bindings, configured_step, verify_step_resources
    from runtime.component_conversion.formats import format_group,format_source_bindings,configured_format
    if not (basic_group(execution['plan'], group) or execution['include_steps'] and step_group(execution['plan'], group)
            or execution['include_formats'] and format_group(execution['plan'],group)):
        raise ValueError('Format wrapper/composition generation is deferred')
    bindings = source_bindings(execution['plan'], group)
    bindings.update(format_source_bindings(execution['plan'],group,execution['units']))
    step = configured_step(execution['plan'], group, execution['units'])
    composed=configured_format(execution['plan'],group,execution['units'])
    if execution['target'] != component_target(profile):
        raise ValueError('Component request does not match current source/configuration/target')
    if payload is not None:
        if payload.get('input_revision') != input_revision(execution['plan'], group, execution['target']) or payload.get('group_id') != identity:
            raise ValueError('Component request identity changed')
        expected = {key: execution['plan'].components[key].model_dump(mode='json') for key in group.members}
        if payload.get('components') != expected:
            raise ValueError('Component request changed qualified component metadata')
        if payload.get('configured_unit') != step:
            raise ValueError('Component request changed the configured step occurrence')
        if payload.get('configured_format')!=composed:
            raise ValueError('Component request changed the configured format structure/direction')
        if step is not None and (payload.get('operation_calls') != step['operation_calls'] or payload.get('service_connections') != sorted(step['service_connections'],key=lambda item:item['connection_id'])):
            raise ValueError('Component request changed occurrence-specific external contracts')
        from runtime.component_conversion.source_evidence import validate_component_sources
        validate_component_sources(execution['plan'], group, bindings, payload.get('sources', []))
        if composed is not None:
            from runtime.component_conversion.format_chains import attach_format_chains
            trusted=dict(configured_format=composed,requirements={})
            attach_format_chains(trusted,execution['plan'],group,execution['units'])
            if any(payload.get(key)!=trusted[key] for key in ('format_chains','format_chain_policy')):
                raise ValueError('Component request changed original decorator order/scope obligations')
    validate_checkpoints(conn, config, profile, execution['classpath'], execution['selected'])
    verify_original_sources(execution['plan'], group)
    if bindings:
        from tools.conversion_tools.component_identity import component_group
        for target in bindings.values(): verify_original_sources(execution['plan'], component_group(execution['plan'], target))
    verify_step_resources(conn, config, profile, step)

