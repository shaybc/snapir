"""Rollout cannot be inferred from preparation, one boundary or incomplete defect checks."""
from copy import deepcopy
from tools.behavior_verification.acceptance_trial_gates import boundaries_passed,rollout_ready
from tools.behavior_verification.thin_path_request import SELECTION


def accepted():
    return dict(units={name:dict(status='accepted',defect_check='passed',observed_cases=3,evidence='retained') for _,name in SELECTION},
        full_operation=dict(acceptance_complete=True,total_operations=1,accepted_operations=1,total_units=7,accepted_units=7))


def test_full_acceptance_required_for_rollout():
    report=accepted()
    assert boundaries_passed(report) and rollout_ready(report)
    report['full_operation']['accepted_operations']=0
    assert not rollout_ready(report)
    report=accepted();report['full_operation']['total_operations']=2
    assert not rollout_ready(report)


def test_every_boundary_needs_actual_cases_and_defect_detection():
    for field,value in [('status','prepared'),('defect_check','incomplete'),('observed_cases',0),('evidence',None)]:
        report=deepcopy(accepted());report['units'][SELECTION[0][1]][field]=value
        assert not boundaries_passed(report) and not rollout_ready(report)
    report=accepted();report['units'].pop(SELECTION[-1][1])
    assert not boundaries_passed(report)
