"""Classify saved conversion outcomes for dashboard filtering, without claiming acceptance."""


def target_status(target):
    """Separate current results from failed historical attempts and policy exclusions."""
    result = target.get('result', 'not established')
    if result == 'external_policy':
        return 'external policy'
    if result == 'configuration_bound':
        return 'configuration bound'
    if result == 'deferred':
        return 'not started'
    if result == 'running':
        return 'running or unknown'
    if result in {'configuration_validated', 'configuration_verified'}:
        return 'completed'
    if result.startswith(('component_validated', 'component validated', 'reused validated component', 'saved unit accepted')):
        return 'completed'
    blocker = target.get('blocker', '')
    if blocker.startswith('not_sent_'):
        return 'blocked'
    if blocker in {'blocked_prerequisite', 'prerequisite_blocked', 'missing_prerequisite'} or any(
            text in target.get('blocker_summary', '').lower() for text in ('prerequisite', 'depends on')):
        return 'blocked'
    if blocker or result.startswith(('incomplete', 'failed', 'stale')):
        return 'failed'
    attempts = target.get('attempts', [])
    if attempts:
        outcome = attempts[-1]['outcome']
        if outcome == 'in_progress_or_unknown':
            return 'running or unknown'
        if outcome != 'saved_validation_passed':
            return 'failed'
        return 'validation recorded'
    if any(check.get('decision') == 'too_large' for check in target.get('budget_checks', [])):
        return 'blocked'
    return 'not started' if target.get('members') else 'unknown'


def target_summary(target):
    """Return a short latest reason, keeping full details in saved materials."""
    if target.get('blocker_summary'):
        return target['blocker_summary']
    attempts = target.get('attempts', [])
    if attempts:
        return attempts[-1].get('error_summary') or attempts[-1]['outcome'].replace('_', ' ')
    if any(check.get('decision') == 'too_large' for check in target.get('budget_checks', [])):
        return 'Request exceeded its character budget; no delivery is established by this check.'
    return target.get('result', 'Not recorded')
