"""Bind ordered format configuration to current native prerequisites without generating code."""
from tools.state_store_tools import component_records as records
from tools.conversion_tools.scoped_reuse.fingerprints import digest
import json


def configuration_group(plan, group):
    """Configuration nodes describe structure; they are not native implementation artifacts."""
    return bool(group.members) and all(plan.components[key].kind == 'format_node' for key in group.members)


def bind_configuration(conn, run_id, plan, group, profile):
    """Freeze a configuration receipt only after all referenced prerequisites are current."""
    from tools.state_store_tools.conversion_components import _dependencies
    from tools.conversion_tools.component_identity import component_target
    if not configuration_group(plan, group) or group.wave is None:
        raise ValueError('Format configuration has unresolved or cyclic prerequisites')
    with records.transaction(conn):
        registered=conn.execute('SELECT fingerprint,target_json FROM conversion_component_plans WHERE run_id=?',(run_id,)).fetchone()
        if registered is None or registered['fingerprint']!=plan.fingerprint or json.loads(registered['target_json'])!=component_target(profile):
            raise ValueError('Register the current component plan before binding format configuration')
        current = records.head(conn, run_id, group.group_id)
        data = dict(input_revision=current['input_revision'], group_id=group.group_id,
            contract_dependencies=_dependencies(conn, run_id, plan, group, 'contract'),
            result_dependencies=_dependencies(conn, run_id, plan, group, 'result'))
        revision = digest(data)
        if current['result_revision'] != revision or current['status'] != 'configuration_bound':
            records.invalidate(conn, run_id, records.consumers(conn, run_id, group.group_id))
            records.write_record(conn, run_id, group.group_id, 'configuration', revision, data)
            conn.execute("UPDATE conversion_component_heads SET status='configuration_bound',contract_revision=?,result_revision=? WHERE run_id=? AND group_id=?",
                         (revision, revision, run_id, group.group_id))
    return data


def verify_configuration(conn, run_id, plan, group):
    """Reject stale configuration receipts and changed dependency revisions, without claiming behavior."""
    from tools.state_store_tools.conversion_components import _dependencies
    current = records.head(conn, run_id, group.group_id)
    if current is None or current['status'] != 'configuration_bound' or current['contract_revision'] != current['result_revision']:
        raise ValueError('Format configuration prerequisite is not current')
    data = records.read_record(conn, run_id, group.group_id, 'configuration', current['result_revision'])
    if data['input_revision'] != current['input_revision'] or data['group_id'] != group.group_id or (
            data['contract_dependencies'] != _dependencies(conn, run_id, plan, group, 'contract') or
            data['result_dependencies'] != _dependencies(conn, run_id, plan, group, 'result')):
        raise ValueError('Format configuration dependency revision changed')
    return data
