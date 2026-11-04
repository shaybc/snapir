"""Retain independently generated fixture and scenario artifacts using existing bounded stages."""
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from agents.behavior_conversion.test_scenarios import FIXTURES,JUNIT,COMPARISON
from runtime.test_assets.validation import validate_bank,validate_suite
from runtime.test_assets.store import publish,load
from tools.conversion_tools.scoped_reuse.fingerprints import digest

_assets=ContextVar('shared_test_assets',default=None)


def enabled(profile):
    """Keep every existing profile on its original preparation path by default."""
    return getattr(getattr(profile,'test_preparation',None),'mode','existing')=='ai_shared_fixtures_v1'


def current():
    """Return assets only within their owning candidate validation."""
    return _assets.get()


@contextmanager
def asset_scope(assets):
    """Prevent fixtures from leaking between candidates or parallel validations."""
    token=_assets.set(assets)
    try:yield
    finally:_assets.reset(token)


def prepare(tasks,payload,production,inventory,prerequisites=(),*,test_scope=None,feedback=None):
    """Use durable calls; scenario changes cannot replenish implementation counters."""
    settings=tasks.profile.test_preparation
    request_limit=settings.request_chars-settings.response_chars
    prerequisites=dict(prerequisites)
    configured=payload.get('configured_format') or payload.get('configured_unit') or payload.get('selected_unit') or payload.get('unit') or payload
    kind=configured.get('kind') or payload.get('kind')
    direction={'response_format':'format','request_unformat':'unformat','configured_step':'step_execute'}.get(kind)
    if direction in {'format','unformat'} and tasks.profile.format_comparison.enabled:
        from runtime.test_assets.original_evidence import complete_format_evidence
        payload=complete_format_evidence(payload,configured,tasks.profile,direction)
    request=dict(original_evidence=payload,boundary_kind=kind,production_files=[f.model_dump(mode='json') for f in production.files],
        prerequisites=dict(prerequisites),parsed_apis=inventory,comparison_case_limit=tasks.profile.format_comparison.max_cases,
        capabilities=['exact_public_entry','dto_construction','typed_list','indexed_context_rows','jdbc_prepared_queries','external_replay'])
    if test_scope:request['required_test_scope']=test_scope
    if payload.get('format_chains'):
        from runtime.component_conversion.format_chain_tests import INSTRUCTION
        request['chain_regression_policy']=INSTRUCTION
    contracts=payload.get('comparison_external_contracts') or configured.get('comparison_external_contracts') or {}
    request['external_contracts']=contracts
    from models.native_unit_bundle import NativeSourceFile
    native_sources=[*production.files,*[NativeSourceFile(path=p,content=t) for p,t in dict(prerequisites).items() if p.startswith('src/main/java/')]]
    original_unit=dict(configured,effective_configuration=configured.get('effective_configuration',dict(attributes={})))
    bank=tasks.ask('fixture_catalog',request,FIXTURES,SharedFixtureBank,
        lambda value:validate_bank(value,payload.get('sources',[]),settings.max_fixture_bytes,
            configuration=original_unit['effective_configuration'],unit=original_unit),request_limit=request_limit)
    if feedback and bank.unresolved:
        from runtime.test_assets.preparation_feedback import fixture_review
        from agents.behavior_conversion.test_scenarios import COLLECTION_RECIPES
        repair_request,repair_check=fixture_review(request,bank,feedback,
            lambda value:validate_bank(value,payload.get('sources',[]),settings.max_fixture_bytes,
                configuration=original_unit['effective_configuration'],unit=original_unit))
        bank=tasks.ask('fixture_catalog',repair_request,FIXTURES+COLLECTION_RECIPES+
            '\nReview the unresolved setup against the supported recipes. Preserve retained fixtures exactly. Clear a reported concern only when it is resolved; otherwise retain it unresolved.',
            SharedFixtureBank,repair_check,request_limit=request_limit)
    with_bank=dict(request,fixture_bank=bank.model_dump(mode='json'))
    def check_junit(value):
        validate_suite(value,bank,settings.max_junit_scenarios,sources=payload.get('sources',[]),native_sources=native_sources,unit=original_unit,api_inventory=inventory)
        if test_scope:
            from runtime.behavior_conversion.native_test_scope import validate_test_scope
            validate_test_scope(dict(calls=[dict(receiver_type=s.native_entry.owner_type,method=s.native_entry.method_name)
                for s in value.scenarios if s.entry_kind=='method']),test_scope)
    from runtime.test_assets.preparation_feedback import junit_for_protocol
    junit_tasks=junit_for_protocol(tasks)
    junit_request,junit_check=dict(with_bank,capabilities=[*with_bank['capabilities'],'native_static_configuration_scope']),check_junit
    junit_instruction=JUNIT
    if feedback:
        from runtime.test_assets.preparation_feedback import prepare_review
        junit_request,junit_check=prepare_review(junit_tasks,junit_request,feedback,check_junit)
        junit_instruction+='\nReview the reported tests-only setup issue against the actual original/native code. Correct invocation and receiver configuration while preserving all retained assertions and scenarios. If the issue is missing production behavior or cannot be resolved with supported setup, report it unresolved. Never change expected behavior to match an accidental default.'
    junit=junit_tasks.ask('junit_scenarios',junit_request,junit_instruction,JunitScenarioSuite,junit_check,request_limit=request_limit)
    # A tests-only role cannot repair a missing fixture. Ask the owning preparation roles,
    # keeping their existing bounded counters and every retained data/assertion baseline.
    for _ in range(tasks.profile.max_agent_task_retries):
        missing=[*junit.unresolved,*[message for s in junit.scenarios for message in s.unresolved]]
        if not missing or bank.unresolved:break
        previous_bank,previous_suite=bank,junit
        feedback=dict(unresolved=missing,retained_fixture_bank=bank.model_dump(mode='json'),retained_junit_scenarios=junit.model_dump(mode='json'))
        def check_repaired_bank(value):
            validate_bank(value,payload.get('sources',[]),settings.max_fixture_bytes,configuration=original_unit['effective_configuration'],unit=original_unit)
            if any(key not in value.fixtures or digest(value.fixtures[key].model_dump(mode='json'))!=digest(entry.model_dump(mode='json')) for key,entry in previous_bank.fixtures.items()):
                raise ValueError('Fixture repair must preserve retained data; add missing entries instead')
        bank=tasks.ask('fixture_catalog',dict(request,preparation_feedback=feedback),FIXTURES+
            '\nResolve the reported missing fixture data. Retain existing fixtures unchanged. If an adapter capability is absent, record it as unresolved; never fabricate a resource.',
            SharedFixtureBank,check_repaired_bank,request_limit=request_limit)
        with_bank=dict(request,fixture_bank=bank.model_dump(mode='json'),preparation_feedback=feedback)
        def check_repaired_suite(value):
            check_junit(value)
            retained={s.scenario_id:s for s in previous_suite.scenarios};updated={s.scenario_id:s for s in value.scenarios}
            if set(retained)-set(updated) or any(not set(s.assertions)<=set(updated[key].assertions) for key,s in retained.items()):
                raise ValueError('Preparation repair cannot remove retained scenarios or assertions')
        junit=junit_tasks.ask('junit_scenarios',dict(with_bank,capabilities=[*with_bank['capabilities'],'native_static_configuration_scope']),JUNIT+
            '\nCorrect fixture references and construction using the retained baseline. Preserve every existing scenario ID and assertion; do not hide unresolved requirements.',
            JunitScenarioSuite,check_repaired_suite,request_limit=request_limit)
        if bank==previous_bank and junit==previous_suite:break
    comparisons=ComparisonScenarioSuite()
    if direction and tasks.profile.format_comparison.enabled:
        comparisons=tasks.ask('comparison_scenarios',with_bank,COMPARISON,ComparisonScenarioSuite,
            lambda value:validate_suite(value,bank,tasks.profile.format_comparison.max_cases,direction=direction,native_sources=native_sources,unit=original_unit,external_contracts=contracts,api_inventory=inventory),request_limit=request_limit)
    from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
    from runtime.test_assets.junit_support import runtime_source_revision
    context=dict(source=digest(payload),production=digest(production.model_dump(mode='json')),prerequisites=digest(prerequisites),apis=digest(inventory),
        preparation=settings.model_dump(mode='json'),conversion_policy=conversion_policy(tasks.profile),runtime=runtime_source_revision(),
        preparation_instructions=digest([FIXTURES,JUNIT,COMPARISON]),
        comparison=tasks.profile.format_comparison.model_dump(mode='json'))
    root,manifest=publish(Path(tasks.config.output_root)/'test-assets',tasks.identity,context,bank,junit,comparisons,
        definition_checks=['schemas','fixture_references','source_citations','scenario_limits','native_api_recipe_policy'])
    manifest_hash=digest(manifest.model_dump(mode='json'))
    return dict(root=str(root),manifest_hash=manifest_hash,bank=bank,junit=junit,comparisons=comparisons)
