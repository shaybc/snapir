"""Bind mapped calls to occurrences and selected or explicitly pinned API contracts."""

from tools.operation_call_tools.ordering import operation_waves
from tools.operation_call_tools.published_calls import call_contract
from tools.state_store_tools.service_api_uses import list_service_uses

REQUIRED_ROLES = ('csRequestFormat', 'csReplyFormat', 'csErrorReplyFormat')


def published_boundaries(conn, run_id):
    """Return exact pinned API candidates; competing applications are not chosen implicitly."""
    result = {}
    for use in list_service_uses(conn, run_id):
        key = use.contract.channel + '/' + use.contract.operation_id
        result.setdefault(key, []).append(use)
    return result


def bind_context_calls(graph, closures, contracts, pins, profile, *, require_published=False):
    """Return occurrence-bound calls and explicit blockers without resolving new targets."""
    bound, issues = {key: [] for key in closures}, {key: [] for key in closures}
    effective = dict(operations={key: {} for key in closures}, calls=[], issues=[])
    for key, closure in closures.items():
        by_note = {step.source.note: step for step in closure.steps}
        for item in graph['issues']:
            if item['operation'] == key:
                issues[key].append(item['detail'])
        for call in (item for item in graph['calls'] if item['caller'] == key):
            step = by_note.get(call['note'])
            expected = [item for item in closure.calls if item['step_note'] == call['note']]
            if step is None or len(expected) != 1 or expected[0].get('target_context') != call['callee']:
                issues[key].append('Call disagrees with selected occurrence/target context: ' + call['note'])
                continue
            target = call['callee']
            selected_target = closures.get(target)
            if selected_target and expected[0]['target_definition_id'] != selected_target.definition_id:
                issues[key].append('Call target definition disagrees with its execution context: ' + target)
                continue
            candidates = pins.get(target, [])
            contract = None
            if len(candidates) > 1:
                issues[key].append('Multiple pinned applications require explicit API selection: ' + target)
            elif candidates:
                if 'application/xml' not in candidates[0].contract.media_types:
                    issues[key].append('Published target API does not support application/xml: ' + target)
                else:
                    contract = call_contract(candidates[0])
            elif selected_target and not require_published:
                contract = contracts[target]
                missing = [role for role in REQUIRED_ROLES if not contract['formats'].get(role)
                           or contract['formats'][role].get('unresolved')]
                if missing:
                    issues[key].append('Target contract is incomplete: ' + target + ': ' + ', '.join(missing))
                    contract = None
                else:
                    effective['calls'].append(call)
            else:
                issues[key].append('Include the required operation or pin its published API: ' + target)
            if getattr(profile, 'conversion_strategy', None) != 'behavior_units':
                issues[key].append('Complex operation calls require native behavior-unit conversion: ' + target)
            if contract is not None:
                contract = {name: value for name, value in contract.items() if name != 'status'}
                bound[key].append(dict(call, occurrence_id=step.source.definition_id,
                    operation_identity=closure.operation_identity, service_contract=contract))
    waves = operation_waves(effective)
    for key, wave in waves.items():
        if wave['cycle_group']:
            issues[key].append('Operation call cycle requires coordinated service contracts: ' + wave['cycle_group'])
    return bound, issues, waves
