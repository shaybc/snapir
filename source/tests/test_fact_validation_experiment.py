"""Explicit facts-disabled tests cannot produce or reuse normal conversion readiness."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.executable_verification_settings import ExecutableVerificationSettings
from models.native_unit_bundle import NativeUnitBundle
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.verification_mode import policy_payload, conversion_version
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from runtime.behavior_conversion.metadata_checklist import mapping_enabled, map_checklist
from runtime.behavior_conversion.conversion_readiness import require_conversion_evidence
from runtime.behavior_conversion.fact_validation_experiment import require_experiment_evidence
from runtime.format_comparison.planning import analyze_unit
from tools.behavior_verification.create_fact_experiment import create_profile
from test_format_comparison_execution import channel_case
from test_behavior_verification_boundaries import boundary_tool


@pytest.fixture(scope='module', autouse=True)
def selected_jdk():
    with java_scope(PipelineConfiguration(java_version=25)):
        yield


def experimental_profile(**kwargs):
    return PipelineConfiguration(java_version=25, executable_verification=dict(mode='conversion_checklist_v1', experimental_disable_facts=True), **kwargs)


def test_test_policy_is_explicit_and_has_a_distinct_reuse_namespace():
    from tools.conversion_tools.component_identity import component_target
    normal = PipelineConfiguration(executable_verification={'mode': 'conversion_checklist_v1'})
    experiment = experimental_profile()
    assert policy_payload(normal)['checklist_mapping'] == 'bounded-required-v1'
    assert policy_payload(experiment)['checklist_mapping'] == 'disabled_for_test'
    assert component_target(normal) != component_target(experiment)
    assert conversion_version(experiment) != conversion_version(normal)
    with pytest.raises(ValueError, match='test profile'):
        ExecutableVerificationSettings(experimental_disable_facts=True)


def test_disabled_mapping_never_opens_tasks_or_reserves_attempts():
    tasks = SimpleNamespace(profile=experimental_profile())
    assert mapping_enabled(tasks, {'parser_checklist': [{'id': 'old'}]}) is False
    assert map_checklist(tasks, {}, None, None) == {}  # No conn/config/model needed: no persistent reservations.


def test_profile_copy_is_isolated_and_does_not_modify_or_start_original(tmp_path):
    source = tmp_path / 'normal.json'
    original = PipelineConfiguration(output_root=str(tmp_path / 'normal-run'), executable_verification={'mode': 'conversion_checklist_v1'})
    source.write_text(original.model_dump_json(), encoding='utf-8'); before = source.read_bytes()
    target = tmp_path / 'experimental.json'; output = tmp_path / 'experiment-run'
    result = create_profile(source, target, output)
    assert source.read_bytes() == before
    assert result.executable_verification.experimental_disable_facts and not result.format_comparison.collect_facts
    assert not output.exists()  # Merely writing a profile cannot create a run or database.
    with pytest.raises(ValueError, match='separate'):
        create_profile(source, tmp_path / 'bad.json', tmp_path / 'normal-run' / 'nested')


def test_factless_experiment_preserves_build_and_receipt_guards(boundary_tool, tmp_path, monkeypatch):
    plan = channel_case()
    boundary = analyze_unit(plan.original_unit, boundary_tool, collect_facts=False)
    assert boundary.parser_checklist is None and boundary.basic_parser_checklist is None
    config = SimpleNamespace(output_root=str(tmp_path / 'generated'))
    bundle = NativeUnitBundle(files=plan.native_sources)
    session = UnitVerificationSession(config, plan.original_unit, boundary, tool=boundary_tool,
                                      executable_settings=experimental_profile().executable_verification)
    def forbidden(*args, **kwargs): raise AssertionError('Fact mapping must not run')
    monkeypatch.setattr('runtime.behavior_conversion.conversion_readiness.validate_unit_static', forbidden)
    result = session.prepare_tests(bundle)
    assert result['mapping_status'] == 'facts_disabled_for_test'
    assert session.static_report.decisions == []
    with pytest.raises(VerificationIncomplete, match='executed JUnit'):
        session.complete(tmp_path, None, bundle, build_validation=dict(build_passed=True, tests_passed=True, test_count=0))
    session.complete(tmp_path, None, bundle, build_validation=dict(build_passed=True, tests_passed=True, test_count=1))
    receipt = session.last_report
    assert receipt['readiness_status'] == 'experimental_only'
    require_experiment_evidence(config, boundary.unit_id, receipt)
    with pytest.raises(ValueError):
        require_conversion_evidence(config, boundary.unit_id, receipt)
    from tools.state_store_tools.db import get_connection, create_all_tables
    from tools.state_store_tools.runs import upsert_run
    from runtime.behavior_conversion.verification_state import record_verification, require_unit_receipts
    from tools.behavior_verification.checklist_mapping import candidate_files
    import hashlib
    config.run_id = 'fact-experiment'
    conn = get_connection(str(tmp_path / 'trial-state.db')); create_all_tables(conn)
    upsert_run(conn, run_id=config.run_id, run_mode='conversion')
    record_verification(conn, config, boundary.unit_id, 'accepted', receipt)
    files = {path: hashlib.sha256(content.encode('utf-8')).hexdigest() for path, content in candidate_files(bundle.files).items()}
    record = dict(bindings={'format': dict(unit_id=boundary.unit_id, files=files)})
    with pytest.raises(ValueError):
        require_unit_receipts(conn, config, record)  # Default/normal assembly cannot consume a trial receipt.
    require_unit_receipts(conn, config, record, expected_version='conversion-facts-experiment-v1')
    conn.close()
    changed = bundle.model_copy(deep=True); changed.files[0].content += '\n'
    with pytest.raises(VerificationFailure, match='Candidate changed'):
        session.complete(tmp_path, None, changed, build_validation=dict(build_passed=True, tests_passed=True, test_count=1))
    static = session.attempt / 'static/unit-static-checks.json'
    static.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        require_experiment_evidence(config, boundary.unit_id, receipt)


def test_normal_policy_still_requires_facts(boundary_tool, tmp_path):
    plan = channel_case()
    boundary = analyze_unit(plan.original_unit, boundary_tool, collect_facts=False)
    session = UnitVerificationSession(SimpleNamespace(output_root=str(tmp_path)), plan.original_unit, boundary,
        tool=boundary_tool, executable_settings=ExecutableVerificationSettings(mode='conversion_checklist_v1'))
    with pytest.raises(VerificationFailure, match='checklist_answers'):
        session.prepare_tests(NativeUnitBundle(files=plan.native_sources))
