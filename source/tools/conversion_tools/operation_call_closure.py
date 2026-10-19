"""Attach operation targets and block incomplete or unsafe service-call conversion."""

from models.conversion_models import ClosureBlockingIssue, ClosureStatus
from tools.operation_call_tools.ordering import operation_waves
from tools.state_store_tools.operation_calls import load_graph, get_contract


def resolve_operation_calls(conn, run_id, operation_id, channel, included_steps, profile):
    """Return calls with saved contracts and actionable blocking issues."""
    graph = load_graph(conn, run_id)
    if graph is None:
        import json
        from tools.operation_call_tools.discovery import COMPLEX_CLASS
        for step in included_steps:
            row = conn.execute("SELECT metadata_json FROM source_artifacts WHERE run_id=? AND kind='opStep' AND logical_id=?", (run_id, step)).fetchone()
            if row and json.loads(row[0]).get('impl_class') == COMPLEX_CLASS:
                return [], [ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
                    entity_id=step, detail='Operation-call graph is missing; refresh vault import before converting CCComplexOpStep')]
        return [], []
    key = channel + '/' + operation_id
    from runtime.intake_plan import has_intake_plan
    if has_intake_plan(conn, run_id):
        from tools.operation_call_tools.published_calls import resolve_published_calls
        return resolve_published_calls(conn, run_id, key, included_steps, graph, profile)
    calls = [dict(call) for call in graph['calls'] if call['caller'] == key and call['step'] in included_steps]
    details = [issue['detail'] for issue in graph['issues'] if issue['operation'] == key]
    waves = operation_waves(graph)
    if key in waves and waves[key]['cycle_group']:
        details.append('Operation call cycle requires coordinated service contracts: ' + waves[key]['cycle_group'])
    if key in waves and waves[key]['wave'] is None and not details:
        details.append('Transitive operation-call dependencies are unresolved')
    for call in calls:
        if getattr(profile, 'conversion_strategy', None) != 'behavior_units':
            details.append('CCComplexOpStep service replacement requires behavior_units conversion: ' + call['step'])
            continue
        try:
            contract = get_contract(conn, run_id, call['callee'])
            required = ('csRequestFormat', 'csReplyFormat', 'csErrorReplyFormat')
            if any(role not in contract['formats'] or contract['formats'][role].get('unresolved') for role in required):
                raise ValueError('Target request/reply/error formats are missing or ambiguous: ' + call['callee'])
            # Readiness changes during assembly; it is not part of the client API.
            contract.pop('status', None)
            call['service_contract'] = contract
        except ValueError as exc:
            details.append(str(exc))
    issues = [ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE, entity_id=key, detail=detail) for detail in details]
    return calls, issues
