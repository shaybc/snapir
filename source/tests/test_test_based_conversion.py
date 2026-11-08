"""Supported fact-free conversion requires executed tests and revision-bound evidence."""
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
from runtime.behavior_conversion.verification_mode import policy_payload, conversion_version
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from runtime.behavior_conversion.conversion_readiness import require_conversion_evidence
from runtime.behavior_conversion.fact_validation_experiment import require_experiment_evidence
from runtime.format_comparison.planning import analyze_unit
from test_format_comparison_execution import channel_case
from test_behavior_verification_boundaries import boundary_tool
from test_fact_validation_experiment import selected_jdk
from test_component_formats import format_case


def test_supported_policy_is_distinct_from_legacy_and_experiments():
    from cli.default_configuration_settings import completed_settings
    from tools.conversion_tools.component_identity import component_target
    from tools.behavior_verification.boundary_contracts import digest
    profile = PipelineConfiguration.model_validate(completed_settings({'source_workspace_id':'bank'}))
    experiment = PipelineConfiguration(executable_verification={'mode':'conversion_checklist_v1','experimental_disable_facts':True})
    legacy = PipelineConfiguration()
    assert not policy_payload(profile)['fact_collection']
    assert policy_payload(profile)['executed_tests_required']
    assert len({conversion_version(p) for p in (profile, experiment)}) == 2
    assert len({digest(component_target(p)) for p in (profile, experiment, legacy)}) == 3


def test_supported_readiness_rejects_missing_tests_changed_code_and_evidence(boundary_tool, tmp_path, monkeypatch):
    plan = channel_case()
    boundary = analyze_unit(plan.original_unit, boundary_tool, collect_facts=False)
    config = SimpleNamespace(output_root=str(tmp_path / 'output'))
    settings = PipelineConfiguration(executable_verification={'mode':'test_based_v1'}).executable_verification
    bundle = NativeUnitBundle(files=plan.native_sources)
    session = UnitVerificationSession(config, plan.original_unit, boundary, tool=boundary_tool, executable_settings=settings)
    def forbidden(*args, **kwargs):
        raise AssertionError('Facts/checklist validation must not run')
    monkeypatch.setattr('runtime.behavior_conversion.conversion_readiness.validate_unit_static', forbidden)
    assert session.prepare_tests(bundle)['mapping_status'] == 'test_based_ready'
    assert session.static_report.decisions == []
    for build in ({}, dict(build_passed=True, tests_passed=True, test_count=0),
                  dict(build_passed=True, tests_passed=False, test_count=1)):
        with pytest.raises(VerificationIncomplete, match='executed JUnit'):
            session.complete(tmp_path, None, bundle, build_validation=build)
    session.complete(tmp_path, None, bundle, build_validation=dict(build_passed=True, tests_passed=True, test_count=1))
    receipt = session.last_report
    assert receipt['verification_version'] == 'test-based-conversion-v1'
    assert receipt['readiness_status'] == 'conversion_ready' and not receipt['experimental_only']
    require_conversion_evidence(config, boundary.unit_id, receipt)
    with pytest.raises(ValueError):
        require_experiment_evidence(config, boundary.unit_id, receipt)
    changed = bundle.model_copy(deep=True); changed.files[0].content += '\n'
    with pytest.raises(VerificationFailure, match='Candidate changed'):
        session.complete(tmp_path, None, changed, build_validation=dict(build_passed=True, tests_passed=True, test_count=1))
    (session.attempt / 'static/unit-static-checks.json').write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        require_conversion_evidence(config, boundary.unit_id, receipt)


@pytest.mark.parametrize('identity', ['request', 'response'])
def test_xml_formats_prepare_without_facts_or_checklist_answers(format_case, identity):
    from runtime.component_conversion.requests import build_component_request
    from runtime.component_conversion.format_verification import format_bundle, session_for
    from models.native_format_component_bundle import NativeFormatComponentBundle
    from tools.conversion_tools.component_identity import component_group
    from test_component_formats import fixture_tree, candidate
    _, config, normal, preparation, plan, _, units = format_case
    profile = normal.model_copy(update={'staged_unit_conversion':True,
        'executable_verification':PipelineConfiguration(executable_verification={'mode':'test_based_v1'}).executable_verification})
    from tools.behavior_verification.boundaries import build_boundary_report
    boundaries = build_boundary_report(preparation, collect_checklists=False)
    request, _ = build_component_request(plan, component_group(plan, plan.unit_roots[identity]), boundaries, [], profile, units=units)
    request, files = fixture_tree(request)
    native = NativeFormatComponentBundle.model_validate(candidate(request))
    native.checklist_answers = None
    bundle = format_bundle(native, request, files)
    session = session_for(config, profile, units[identity], boundaries['boundaries'][identity])
    assert session.prepare_tests(bundle)['mapping_status'] == 'test_based_ready'
