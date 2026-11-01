"""Compare recognized harness logs by severity/count while retaining raw diagnostics."""
from collections import Counter


LOGGING_POLICY = dict(
    version='logging-severity-count-v1',
    blocking='count_per_numeric_severity_per_input',
    diagnostic_only=['message_and_values', 'logger_identity', 'method_overload',
                     'attached_exception', 'event_order'],
    unknown_events='strict_external_call_comparison',
    limitation='Matching severity/count does not establish equivalent message content or conditions.')

_LOGGER = 'logging:java.util.logging.Logger.'
_LEVELS = {'severe': 1000, 'warning': 900, 'info': 800, 'fine': 500}


def _severity(event):
    """Recognize only supported Logger calls recorded by the existing harness."""
    target, arguments = event.get('target'), event.get('arguments')
    if not isinstance(target, str) or not isinstance(arguments, list):
        return None
    for method, level in _LEVELS.items():
        if target == _LOGGER + method + '(java.lang.String)' and len(arguments) == 1:
            return level
    if target.startswith(_LOGGER + 'log(java.util.logging.Level, ') and target.endswith(')') and len(arguments) >= 2:
        level = arguments[0]
        if isinstance(level, dict) and isinstance(level.get('$logging_level'), str) and type(level.get('value')) is int:
            return level['value']
    return None


def _partition(events):
    business, logs, counts = [], [], Counter()
    for index, event in enumerate(events):
        severity = _severity(event)
        if severity is None:
            business.append(event)
        else:
            counts[str(severity)] += 1
            logs.append(dict(event_index=index, event=event))
    return business, logs, counts


def compare_logging(legacy, native):
    """Return strict non-log events, blocking severity counts and diagnostic raw logs.

    The input sequences are never mutated. Original indexes preserve evidence of
    ordering relative to business calls, although logging order is not a gate.
    """
    left, left_logs, left_counts = _partition(legacy)
    right, right_logs, right_counts = _partition(native)
    differences = [dict(path='logging.severity_counts.' + severity,
        legacy=left_counts[severity], native=right_counts[severity],
        reason='Logging event count differs at numeric severity ' + severity)
        for severity in sorted(set(left_counts) | set(right_counts)) if left_counts[severity] != right_counts[severity]]
    diagnostics = []
    if left_logs != right_logs:
        diagnostics.append(dict(kind='logging_details_differ', blocking=False,
            policy_version=LOGGING_POLICY['version'], legacy=left_logs, native=right_logs,
            note='Raw message, values, logger, overload, exception and order differences are diagnostic only.'))
    return left, right, differences, diagnostics
