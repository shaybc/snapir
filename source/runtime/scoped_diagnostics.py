"""Extract actionable qualified-preparation blockers for logs and saved-status displays."""


def preparation_blockers(report):
    """Return distinct operation-qualified reasons without interpreting readiness as generation approval."""
    reasons = []
    if report.get('preparation_error'):
        reasons.append(str(report['preparation_error']))
    for key, item in report.get('operations', {}).items():
        reasons.extend(key + ': ' + str(reason) for reason in item.get('blockers', []))
    return list(dict.fromkeys(reasons))
