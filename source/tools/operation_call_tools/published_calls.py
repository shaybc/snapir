"""Adapt pinned published APIs to the existing CCComplex HTTP-generation contract."""

import hashlib
import json
from models.conversion_models import ClosureBlockingIssue, ClosureStatus
from tools.state_store_tools.service_api_uses import list_service_uses


def call_contract(use):
    """Expose saved request, reply, error and address details without reading callee source."""
    service = use.contract
    payload = use.model_dump(mode='json')
    property_name = use.address.base_url_property or 'operations.' + hashlib.sha256(
        (service.channel + '/' + service.operation_id).encode()).hexdigest()[:12] + '.base-url'
    return dict(operation=service.channel + '/' + service.operation_id, method=service.method,
        path=service.path, media_type='application/xml', base_url_property=property_name,
        configured_base_url=str(use.address.base_url) if use.address.base_url else None,
        address=use.address.model_dump(mode='json'),
        formats=dict(csRequestFormat=service.request_contract, csReplyFormat=service.response_contract,
                     csErrorReplyFormat=service.error_contract),
        published_api=True, api_revision=service.api_revision, application_id=service.application_id,
        fingerprint=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        error_policy=service.api_definition.get('error_policy', 'Use the saved target error contract.'))


def resolve_published_calls(conn, run_id, key, included_steps, graph, profile):
    """Resolve calls only against this run's pinned trusted APIs; return actionable blockers."""
    uses = {use.contract.channel + '/' + use.contract.operation_id: use for use in list_service_uses(conn, run_id)}
    calls, details = [], []
    candidates = [call for call in graph['calls'] if call['caller'] == key]
    for issue in graph['issues']:
        if issue['operation'] == key:
            if issue.get('callee'):
                candidates.append(dict(issue, caller=key))
            else:
                details.append(issue['detail'])
    for call in candidates:
        if call['step'] not in included_steps:
            continue
        use = uses.get(call['callee'])
        if use is None:
            details.append('Complete and publish the required operation first: ' + call['callee'])
        elif 'application/xml' not in use.contract.media_types:
            details.append('Published target API format is not supported by the native XML converter: ' + call['callee'])
        elif getattr(profile, 'conversion_strategy', None) != 'behavior_units':
            details.append('Published operation calls require native conversion')
        else:
            calls.append(dict(call, service_contract=call_contract(use)))
    return calls, [ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE, entity_id=key, detail=detail) for detail in details]


def verify_pinned_call(conn, run_id, call):
    """Check the caller's saved binding, without revalidating or inspecting the callee."""
    for use in list_service_uses(conn, run_id):
        if use.contract.channel + '/' + use.contract.operation_id == call['callee']:
            if call_contract(use) != call['service_contract']:
                raise ValueError('Pinned API binding changed; regenerate this caller')
            return
    raise ValueError('Pinned published API binding is missing: ' + call['callee'])
