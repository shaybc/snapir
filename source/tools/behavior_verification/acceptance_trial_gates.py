"""Acceptance trial gates never infer operation acceptance from individual boundary results."""
from tools.behavior_verification.thin_path_request import SELECTION


def boundaries_passed(report):
    """Require every selected boundary's technical receipt and completed defect detection."""
    names={name for _,name in SELECTION}
    return set(report.get('units',{}))==names and all(
        item.get('status')=='accepted' and item.get('defect_check')=='passed' and item.get('observed_cases',0)>0
        and bool(item.get('evidence')) for item in report['units'].values())


def rollout_ready(report):
    """Default-mode rollout requires verified full-operation acceptance after the boundary trials."""
    full=report.get('full_operation',{})
    return (boundaries_passed(report) and full.get('acceptance_complete') is True
        and full.get('total_operations')==1 and full.get('accepted_operations')==1
        and full.get('total_units',0)>0 and full.get('accepted_units')==full['total_units'])
