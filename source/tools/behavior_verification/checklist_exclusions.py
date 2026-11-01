"""Deterministic exclusions; observed success and AI assertions are never proof."""
from models.checklist_exclusion_authorization import ChecklistExclusionAuthorization
from tools.behavior_verification.boundary_contracts import digest


def validate_exclusion(item, answer, boundary, candidate_hash, policy, proofs, authorizations):
    """Return a proof receipt or reject this exact checklist exclusion."""
    if answer.reason == 'approved_exception':
        matches = [ChecklistExclusionAuthorization.model_validate(value) for value in authorizations
                   if (value.get('approval_id') if isinstance(value, dict) else value.approval_id) == answer.approval_id]
        if len(matches) != 1:
            raise ValueError('Exclusion requires one separately supplied approval')
        approval = matches[0]
        if (approval.unit_id, approval.source_manifest_hash, approval.configuration_hash, approval.candidate_hash, approval.checklist_id) != (
            boundary.unit_id, boundary.source_manifest_hash, boundary.configuration_hash, candidate_hash, item.id):
            raise ValueError('Exclusion approval does not match this item and revision')
        receipt = approval.model_dump(mode='json')
        return dict(reason=answer.reason, authorization=receipt, authorization_hash=digest(receipt))
    if answer.reason == 'framework_plumbing':
        node = next((node for node in boundary.reachable_slice.nodes if node.id == item.code_node_id), None)
        rules = {
            'implicit_constructor_marker': item.kind == 'initialization' and item.detail == 'implicit_constructor' and node is not None and node.kind == 'implicit_constructor',
            'configured_setup_marker': item.kind == 'initialization' and item.detail == 'configured_setup_method',
            'throws_declaration_metadata': item.kind == 'exception' and item.detail == 'declared',
        }
        if answer.rule_id in policy.plumbing_rules and rules.get(answer.rule_id):
            return dict(reason=answer.reason, rule_id=answer.rule_id, scope='metadata_marker_only')
    proof = proofs.get(item.id)
    if proof and answer.reason == proof['reason'] and (not answer.rule_id or answer.rule_id == proof['rule_id']):
        return proof
    raise ValueError('Unsupported exclusion; provide implementation or a separately approved exact-item exception')
