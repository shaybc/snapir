"""Map explicit AI scenarios to the existing isolated boundary execution protocol."""
from models.format_comparison_case import FormatComparisonCase
from models.format_comparison_plan import FormatComparisonEntry,FormatComparisonPlan
from runtime.test_assets.references import resolve


def controls(bank, scenario, manifest_hash):
    """Create independent logical controls; JVMs construct fresh resource instances."""
    return dict(inputs={key:resolve(bank,ref) for key,ref in scenario.inputs.items()},
        resources={key:resolve(bank,ref) for key,ref in scenario.resources.items()},
        composer_resource_setters=getattr(scenario,'composer_resource_setters',{}),manifest_hash=manifest_hash)


def comparison_plan(label, unit, sources, bank, suite, manifest_hash):
    """Explicit comparison scenarios never trigger deterministic fixture expansion."""
    entries={};cases=[]
    for scenario in suite.scenarios:
        if unit.get('kind')!='configured_step':
            from runtime.test_assets.resource_bindings import validate_comparison_resources
            validate_comparison_resources(scenario)
        entries[scenario.scenario_id]=FormatComparisonEntry(direction=scenario.direction,binding=scenario.native_entry)
        cases.append(FormatComparisonCase(case_id=scenario.scenario_id,binding_id=scenario.scenario_id,
            initial_context={key:resolve(bank,ref) for key,ref in scenario.composer_context.items()},
            input_xml=resolve(bank,scenario.input_xml) if scenario.input_xml else None,
            settings=resolve(bank,scenario.settings) if scenario.settings else [],
            external_responses=resolve(bank,scenario.external_responses) if scenario.external_responses else [],
            clock_millis=scenario.clock_millis,random_seed=scenario.random_seed,
            test_assets=controls(bank,scenario,manifest_hash),scenario_unresolved=[*bank.unresolved,*suite.unresolved,*scenario.unresolved],
            observe_context_keys=scenario.observe_context_keys))
    from models.step_comparison_plan import StepComparisonPlan
    schema=StepComparisonPlan if unit.get('kind')=='configured_step' else FormatComparisonPlan
    plan=schema(label=label,scope='configured',original_unit=unit,native_sources=sources,
        entries=entries,cases=cases,explicit_scenarios=True,fixture_manifest_hash=manifest_hash)
    plan.original_framework.external_bindings=dict(suite.legacy_external_bindings)
    plan.native_external_bindings=dict(suite.native_external_bindings)
    return plan
