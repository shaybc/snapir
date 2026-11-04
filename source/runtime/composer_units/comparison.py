"""Share original-unit preparation between converter diagnostics and standalone comparisons."""
import json
from pathlib import Path
from models.composer_unit_specification import ComposerUnitSpecification
from runtime.composer_units.packaging import prepare
from tools.behavior_verification.boundary_contracts import digest


def setup_key(unit,direction):
    """Configuration variants must never execute a package initialized for another variant."""
    return 'setup:'+digest([direction,unit['effective_configuration'],unit.get('configuration_xml',''),unit.get('referenced_definitions',[])])


def prepare_comparison(plan,profile,directory):
    """Return a derived plan; never rewrite saved original/native artifacts or operation steps."""
    if plan.original_unit.get('kind')=='configured_step':return plan
    result=plan.model_copy(deep=True)
    from runtime.format_comparison.planning import unit_for_case
    selected=[(direction,plan.original_unit,True) for direction in sorted({entry.direction for entry in plan.entries.values()})]
    selected.extend((plan.entries[case.binding_id].direction,unit_for_case(plan,case),False) for case in plan.cases)
    for direction,unit,baseline in selected:
        key=setup_key(unit,direction)
        if key in result.original_packages:continue
        outcome=prepare(ComposerUnitSpecification(action=direction,unit=unit,framework=plan.original_framework),profile,directory)
        if outcome.status!='package_ready':raise ValueError('Original Composer preparation unavailable: '+'; '.join(outcome.issues))
        result.original_packages[key]=outcome.package
        if baseline:
            result.original_packages[direction]=outcome.package
            result.original_unit=json.loads((Path(outcome.package)/'unit.json').read_text())
    return result
