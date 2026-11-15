"""Comparison opt-out preserves generated-code checks and separates reuse policies."""
from types import SimpleNamespace
import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.verification_mode import (comparison_testing_enabled, format_comparison_enabled,
    verification_settings, executable_mode, conversion_mode, policy_payload)


@pytest.mark.parametrize('mode', ['checklist_v1', 'executable_boundary_v1', 'conversion_checklist_v1', 'test_based_v1'])
def test_disabled_comparisons_use_conversion_readiness_without_mutating_saved_mode(mode):
    profile = PipelineConfiguration(comparison_testing_enabled=False, executable_verification={'mode': mode},
                                    format_comparison={'enabled': True})
    assert not comparison_testing_enabled(profile)
    assert not format_comparison_enabled(profile)
    assert conversion_mode(profile) and not executable_mode(profile)
    assert verification_settings(profile).mode in {'conversion_checklist_v1', 'test_based_v1'}
    assert profile.executable_verification.mode == mode
    assert policy_payload(profile)['comparison_testing_enabled'] is False
    assert policy_payload(profile)['equivalence'] == 'not_assessed'


def test_default_and_detailed_diagnostic_settings_are_preserved():
    profile = PipelineConfiguration(format_comparison={'enabled': True})
    assert profile.comparison_testing_enabled
    assert format_comparison_enabled(profile)
    assert verification_settings(profile) is profile.executable_verification
    assert 'comparison_testing_enabled' not in policy_payload(profile)
    assert not format_comparison_enabled(profile.model_copy(update={
        'format_comparison': profile.format_comparison.model_copy(update={'enabled': False})}))


@pytest.mark.parametrize('choice, expected', [('enabled', True), ('disabled', False)])
def test_default_wizard_exposes_comparison_choice(choice, expected, tmp_path):
    from cli.default_configuration_flow import collect_section
    draft = SimpleNamespace(section=6, values=lambda: {})
    inputs = SimpleNamespace(text=lambda *_args: '', menu=lambda *_args: choice)
    api = SimpleNamespace(collect_gate_configuration=lambda *_args: {'plan_approval_policy': 'human'})
    result = collect_section(draft, inputs, tmp_path, api)
    assert result['comparison_testing_enabled'] is expected
    assert result['plan_approval_policy'] == 'human'


def test_disabled_format_and_step_diagnostics_never_prepare_or_execute(monkeypatch, tmp_path):
    from runtime.format_comparison.component_diagnostics import diagnose_component
    from runtime.step_comparison.component_diagnostics import diagnose_step
    from runtime.format_comparison.runner import run_comparison
    from runtime.format_comparison.preparation import prepare_plan
    profile = PipelineConfiguration(comparison_testing_enabled=False, format_comparison={'enabled': True},
                                    test_preparation={'mode': 'ai_shared_fixtures_v1'})
    validator = SimpleNamespace(profile=profile, request={'configured_format': {'unit_id': 'format'}})
    monkeypatch.setattr('runtime.format_comparison.component_diagnostics._diagnose_component',
                        lambda *_args, **_kwargs: pytest.fail('Original/native comparison ran'))
    assert diagnose_component(validator, None, {}, tmp_path / 'format') is None
    assert diagnose_step(validator, {}, tmp_path / 'step', []) is None
    with pytest.raises(ValueError, match='disabled'):
        run_comparison(None, profile, tmp_path / 'execution')
    with pytest.raises(ValueError, match='disabled'):
        prepare_plan('format', 'configured', {}, [], [], profile, tmp_path / 'preparation')
    assert not (tmp_path / 'step').exists()
    assert not (tmp_path / 'execution').exists()


def test_component_session_and_unit_generation_receive_non_comparison_policy(monkeypatch):
    from runtime.component_conversion.format_verification import session_for
    from runtime.behavior_conversion import verification_units
    profile = PipelineConfiguration(comparison_testing_enabled=False, executable_verification={'mode': 'executable_boundary_v1'})
    captured = []
    def session(*args, **kwargs):
        captured.append(kwargs['executable_settings'])
        raise RuntimeError('session policy captured')
    monkeypatch.setattr('runtime.component_conversion.format_verification.UnitVerificationSession', session)
    monkeypatch.setattr('runtime.component_conversion.format_verification.UnitVerificationBoundary.model_validate', lambda value: value)
    with pytest.raises(RuntimeError, match='captured'):
        session_for(None, profile, {}, {})
    monkeypatch.setattr(verification_units, 'UnitVerificationSession', session)
    monkeypatch.setattr(verification_units, 'attach_verification', lambda *_args, **_kwargs: ({}, {}, {}))
    config = SimpleNamespace(run_id='run')
    with pytest.raises(RuntimeError, match='captured'):
        verification_units.generate_verified_unit(None, config, profile, 'unit', '', {}, None)
    assert [value.mode for value in captured] == ['conversion_checklist_v1'] * 2


def test_switch_changes_local_and_shared_reuse_identity_without_changing_source(tmp_path):
    from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy, checkpoint_policy
    from runtime.component_conversion.shared_identity import implementation_identity
    enabled = PipelineConfiguration(executable_verification={'mode': 'test_based_v1'})
    disabled = enabled.model_copy(update={'comparison_testing_enabled': False})
    node = SimpleNamespace(kind='java_implementation', label='example.Format', roles=['format_leaf'],
                           provenance={'source_hash': 'source-1'}, dependencies=[])
    plan = SimpleNamespace(components={'format': node})
    group = SimpleNamespace(members=['format'])
    assert conversion_policy(enabled) != conversion_policy(disabled)
    assert checkpoint_policy(enabled) == checkpoint_policy(disabled)
    assert implementation_identity(plan, group, enabled) != implementation_identity(plan, group, disabled)
    assert implementation_identity(plan, group, enabled) == implementation_identity(plan, group,
        PipelineConfiguration.model_validate_json(enabled.model_dump_json()))


def test_disabled_comparisons_keep_native_scenario_preparation(monkeypatch, tmp_path):
    from runtime.test_assets.preparation import prepare
    from models.shared_test_fixture import SharedFixtureBank
    from models.junit_test_scenario import JunitScenarioSuite
    from models.native_unit_bundle import NativeUnitBundle
    calls = []
    profile = PipelineConfiguration(comparison_testing_enabled=False, format_comparison={'enabled': True},
                                    test_preparation={'mode': 'ai_shared_fixtures_v1'})
    def ask(stage, request, instruction, schema, check, **kwargs):
        calls.append(stage)
        assert stage != 'comparison_scenarios'
        return SharedFixtureBank(fixtures={'flag': {'value': True}}) if stage == 'fixture_catalog' else JunitScenarioSuite(
            scenarios=[dict(scenario_id='native', purpose='Native behavior',
                            native_entry=dict(owner_type='nativecode.Sample', method_name='run', arguments=[]),
                            assertions=['run returns true'])])
    tasks = SimpleNamespace(profile=profile, config=SimpleNamespace(output_root=str(tmp_path)), identity='unit', ask=ask)
    monkeypatch.setattr('runtime.test_assets.original_evidence.complete_format_evidence',
                        lambda *_args: pytest.fail('Comparison evidence discovery ran'))
    monkeypatch.setattr('runtime.test_assets.preparation_feedback.junit_for_protocol', lambda tasks: tasks)
    result = prepare(tasks, {'configured_format': {'kind': 'request_unformat', 'unit_id': 'unit'}},
                     NativeUnitBundle(files=[dict(path='src/main/java/nativecode/Sample.java',
                         content='package nativecode; public class Sample { public boolean run() { return true; } }')]), {}, {})
    assert calls == ['fixture_catalog', 'junit_scenarios']
    assert result['comparisons'].scenarios == []


def test_disabled_comparisons_still_require_successful_build_and_executed_native_tests(monkeypatch, tmp_path):
    from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    from models.native_unit_bundle import NativeUnitBundle
    from tools.behavior_verification.checklist_mapping import candidate_digest, candidate_files
    bundle = NativeUnitBundle(files=[dict(path='src/main/java/Sample.java', content='public class Sample {}')])
    profile = PipelineConfiguration(comparison_testing_enabled=False)
    session = UnitVerificationSession.__new__(UnitVerificationSession)
    session.executable_settings = verification_settings(profile)
    session.attempt = tmp_path
    session.unit = {'unit_id': 'unit'}
    session.tool = tmp_path / 'tool.jar'
    session.tool.write_bytes(b'tool')
    (tmp_path / 'static').mkdir()
    (tmp_path / 'static/unit-static-checks.json').write_text('{}')
    session.static_report = SimpleNamespace(status='mapping_valid', candidate_hash=candidate_digest(candidate_files(bundle.files)),
        source_manifest_hash='source', configuration_hash='configuration', policy_hash='policy', tool_hash='tool')
    monkeypatch.setattr(session, 'compare', lambda *_args, **_kwargs: pytest.fail('Original execution ran'))
    for build in ({}, dict(build_passed=True, tests_passed=False, test_count=1),
                  dict(build_passed=True, tests_passed=True, test_count=0)):
        with pytest.raises(VerificationIncomplete, match='executed JUnit'):
            session.complete(tmp_path, None, bundle, build_validation=build)
    session.complete(tmp_path, None, bundle, build_validation=dict(build_passed=True, tests_passed=True, test_count=1))
    assert session.last_report['readiness_status'] == 'conversion_ready'
    assert session.last_report['behavioral_equivalence'] == 'not_assessed'
