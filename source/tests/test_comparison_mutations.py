"""Mutation strength is advisory, bounded, and classified from actual execution evidence."""
from types import SimpleNamespace
import pytest
from models.comparison_mutation_settings import ComparisonMutationSettings
from tools.behavior_verification.comparison_mutations import classify_mutation


@pytest.mark.parametrize('status,touched,issues,expected',[
    ('differences_found',True,[],'detected'),('matched_observed_cases',True,[],'survived'),
    ('matched_observed_cases',False,[],'uncovered'),('verification_incomplete',True,[],'tool_failure'),
    ('verification_incomplete',False,['Work.java:3: error: incompatible types'],'invalid'),
    ('verification_incomplete',False,['Harness could not start'],'tool_failure')])
def test_classification_requires_actual_site_evidence(status,touched,issues,expected):
    report=SimpleNamespace(status=status,issues=issues,cases=[{'native':{'probes':[{'id':'m'}] if touched else []}}])
    assert classify_mutation(report,'m')==expected


def test_limits_and_opt_in_policy():
    assert not ComparisonMutationSettings().enabled
    assert ComparisonMutationSettings().timeout_seconds==600
    for value in (0,33):
        with pytest.raises(ValueError):ComparisonMutationSettings(max_mutants=value)
    with pytest.raises(ValueError):ComparisonMutationSettings(timeout_seconds=0)


def test_worker_timeout_preserves_advisory_result(monkeypatch,tmp_path):
    from runtime.behavior_conversion.comparison_strength import measure_comparisons
    from models.executable_verification_settings import ExecutableVerificationSettings
    from models.boundary_harness_binding import BoundaryHarnessBinding
    session=SimpleNamespace(attempt=tmp_path,unit={},boundary=SimpleNamespace(model_dump=lambda **_:{}),
        executable_structure={'candidate_hash':'unchanged'},executable_settings=ExecutableVerificationSettings(
            comparison_mutations={'enabled':True,'timeout_seconds':0.01}))
    monkeypatch.setattr('runtime.behavior_conversion.comparison_strength.run_mutations',lambda *args:(-1,'timeout',True))
    result=measure_comparisons(session,BoundaryHarnessBinding(adapter_class='A'),BoundaryHarnessBinding(adapter_class='B'),[],tmp_path/'tool.jar')
    assert result['status']=='timed_out' and not result['affects_acceptance']


def test_mutation_scope_excludes_tests_and_other_units(monkeypatch,tmp_path):
    from xml.etree import ElementTree as ET
    from models.boundary_harness_binding import BoundaryHarnessBinding
    from tools.behavior_verification.comparison_mutation_sources import generate_mutations
    paths=['src/main/java/Work.java','src/main/java/Dependency.java','src/test/java/WorkTest.java']
    binding=BoundaryHarnessBinding(adapter_class='Work',sources=[{'path':path,'content':'class Work {}'} for path in paths])
    def parser(*args,**kwargs):
        assert [node.get('path') for node in ET.parse(tmp_path/'mutation-input.xml').getroot()]==paths[:1]
        (tmp_path/'mutation-plans.xml').write_text('<mutations/>')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('tools.behavior_verification.comparison_mutation_sources.run_java',parser)
    assert generate_mutations(binding,tmp_path/'tool.jar',tmp_path,4,[paths[0],paths[2]])==[]


def test_disabled_measurement_does_not_start_work(tmp_path):
    from runtime.behavior_conversion.comparison_strength import measure_comparisons
    from models.executable_verification_settings import ExecutableVerificationSettings
    session=SimpleNamespace(attempt=tmp_path,executable_settings=ExecutableVerificationSettings())
    assert measure_comparisons(session,None,None,[],None) is None
    assert not (tmp_path/'comparison-strength').exists()
