"""Recompute new-policy comparison decisions from retained independent observations."""
from models.boundary_observation import BoundaryObservation
from models.native_verification_binding import NativeVerificationBinding
from tools.behavior_verification.independent_comparison import VERSION,compare_case,summarize
from tools.behavior_verification.boundary_logging import LOGGING_POLICY


def require_observed_agreement(structure,receipt,report):
    """A matching label cannot replace the actual output/state comparison at packaging time."""
    if (structure['comparison_policy']!=VERSION or report.execution_environment.get('comparison_policy')!=VERSION
        or report.logging_comparison_policy!=LOGGING_POLICY):
        raise ValueError('Independent comparison policy changed or is unsupported')
    binding=NativeVerificationBinding.model_validate(receipt['binding'])
    for case in report.cases:
        if any(case[side].get('invocation_completed') is not True for side in ('legacy','native')):
            raise ValueError('Independent boundary invocation was not proven complete')
        outcome=compare_case(case['case']['case_id'],BoundaryObservation.model_validate(case['legacy']),
            BoundaryObservation.model_validate(case['native']),binding,xml_output=structure['kind']=='response_format')
        if outcome['comparison_status']!='matched' or any(case.get(key)!=outcome[key]
            for key in ('comparison_status','differences','limitations','field_results')):
            raise ValueError('Independent observations do not establish a complete match')
    expected=summarize(report)
    if expected!=report.execution_environment.get('comparison_summary') or receipt.get('comparison_summary')!=expected:
        raise ValueError('Independent comparison summary does not match observed cases')
