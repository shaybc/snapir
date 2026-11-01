"""Generate source/configuration-driven boundary cases and explicit settings permutations."""
import hashlib
import itertools
import json
from tools.behavior_verification.controlled_inputs import generate_boundary_cases
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete


def controlled_cases(unit, boundary, binding, controls, *, executable_settings=None, generation_report=None):
    """Exercise every provided settings switch; a model cannot select only a favorable setting."""
    try:
        if executable_settings is not None and executable_settings.mode=='executable_boundary_v1':
            from tools.behavior_verification.input_scenarios import generate_input_scenarios
            cases,report=generate_input_scenarios(unit,boundary,executable_settings)
            if generation_report is not None:generation_report.update(report)
        else:cases = generate_boundary_cases(unit, boundary)
    except ValueError as error:
        raise VerificationIncomplete(dict(stage='cases', errors=[str(error)])) from error
    destinations = binding.settings_bindings
    expected = {control['target']: int(control['arity']) for control in controls}
    if set(destinations) != set(expected):
        raise VerificationFailure(dict(stage='cases', errors=['Bind every source-defined Set settings API'], expected_settings=controls))
    result = cases
    for target, arity in sorted(expected.items()):
        expanded = []
        owner, method = target.rsplit('.', 1)
        for case in result:
            values = sorted({value.lower() for value in case.initial_context.values() if isinstance(value, str)})
            for flags in itertools.product((False, True), repeat=arity):
                limit=executable_settings.max_cases if executable_settings is not None else 512
                if executable_settings is not None and len(expanded)>=limit:
                    raise VerificationIncomplete(dict(stage='cases',errors=['Settings/input product exceeds case budget']))
                setting = dict(**{'class': owner}, method=method, arguments=[values if flag else [] for flag in flags])
                data = case.model_dump(mode='json'); data['settings'] = [*data['settings'], setting]
                data['case_id'] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:20]
                expanded.append(type(case).model_validate(data))
        result = expanded
    limit=executable_settings.max_cases if executable_settings is not None else 512
    if not result or len(result) > limit:
        raise VerificationIncomplete(dict(stage='cases', errors=['Automatic case budget/shape requires a supported case adapter'], case_count=len(result)))
    if executable_settings is not None and any(len(case.model_dump_json())>executable_settings.max_case_chars for case in result):
        raise VerificationIncomplete(dict(stage='cases',errors=['Controlled case/settings size budget exceeded']))
    if generation_report is not None:generation_report.update(planned_cases=len(result),settings_targets=sorted(expected))
    return result
