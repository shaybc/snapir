"""Bind generation to selected, fresh scoped checkpoints for one runtime invocation."""

from contextlib import contextmanager
from contextvars import ContextVar

from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints

_execution = ContextVar('scoped_native_execution', default=None)
_categories = {'unit', 'service', 'service_implementation', 'route_test_plan', 'route_scenario_test', 'review', 'analysis'}


@contextmanager
def native_execution(conn, config, profile, classpath, by_operation):
    """Permit only exact selected operation/unit tasks; never bypass the global guard."""
    if profile.scoped_native_mode != 'behavior_units_v1' or profile.conversion_strategy != 'behavior_units':
        raise ValueError('Unsupported scoped native profile')
    selected = set(by_operation)
    validate_checkpoints(conn, config, profile, classpath, selected)
    identities = {key: (key, sorted(unit.unit_id for unit in own)[0]) for key, own in by_operation.items()}
    identities.update({unit.unit_id: (key, unit.unit_id) for key, own in by_operation.items() for unit in own})
    token = _execution.set(dict(conn=conn, run_id=config.run_id, profile=profile, classpath=classpath,
                               selected=selected, identities=identities))
    try:
        yield
    finally:
        _execution.reset(token)


def require_task(conn, config, profile, category, identity, payload):
    """Recheck context proof before model calls or any accepted-result lookup."""
    execution = _execution.get()
    if not execution or execution['conn'] is not conn or execution['run_id'] != config.run_id:
        raise ValueError('Scoped conversion is gated outside a qualified native execution')
    if execution['profile'] is not profile or category not in _categories:
        raise ValueError('Unsupported scoped generation task/profile')
    matches = [name for name in execution['identities'] if identity == name or identity.startswith(name + ':')]
    if not matches and category == 'analysis' and payload.get('unit_id') in execution['identities']:
        matches = [payload['unit_id']]
    if not matches:
        raise ValueError('Generation task is outside the selected scoped identities: ' + identity)
    key, unit = execution['identities'][max(matches, key=len)]
    validate_checkpoints(conn, config, profile, execution['classpath'], execution['selected'])
    return execution, key, unit


def verify_context(conn, config, profile, key):
    """Validate qualified evidence at downstream packaging or service-call boundaries."""
    from tools.source_discovery_tools.classpath import discover_java_classpath
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    validate_checkpoints(conn, config, profile, classpath, {key})
