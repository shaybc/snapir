"""Keep nested JUnit execution visible without treating aggregate totals as extra cases."""
from types import SimpleNamespace
import pytest
from runtime.behavior_conversion.validation import build_candidate


def validate(tmp_path, reports):
    folder=tmp_path/'target/surefire-reports';folder.mkdir(parents=True)
    for name,text in reports.items():(folder/name).write_text(text,encoding='utf-8')
    context=SimpleNamespace(allowed_ibm_artifacts=[],verifier=SimpleNamespace(
        compile_project=lambda *a,**k:SimpleNamespace(returncode=0,stdout='',stderr='')))
    return build_candidate(tmp_path,context,required_tests=['src/test/java/example/OuterTest.java'])


def test_nested_display_suites_and_duplicate_reports_count_cases_once(tmp_path):
    case='<testcase classname="example.OuterTest$Nested" name="preserves"/>'
    result=validate(tmp_path,{'TEST-example.OuterTest.xml':'<testsuite name="example.OuterTest" tests="0"><testsuite name="Display name" tests="1">'+case+'</testsuite></testsuite>',
        'TEST-example.OuterTest$Nested.xml':'<testsuite name="Display name" tests="1">'+case+'</testsuite>'})
    assert result.tests_passed and result.test_count==1 and not result.issues


@pytest.mark.parametrize('body',[
    '<testsuite name="Display" tests="1"><testcase classname="example.OuterTest$Nested" name="bad"><failure/></testcase></testsuite>',
    '<testsuite tests="1" skipped="1"><testcase name="skipped"><skipped/></testcase></testsuite>',
    '<testsuite tests="0"/>',
])
def test_failed_skipped_or_empty_nested_suites_do_not_pass(tmp_path,body):
    result=validate(tmp_path,{'TEST-example.OuterTest.xml':body})
    assert not result.tests_passed and result.issues


def test_counter_only_aggregate_wrapper_is_not_double_counted(tmp_path):
    result=validate(tmp_path,{'TEST-example.OuterTest.xml':'<testsuites tests="2"><testsuite name="example.OuterTest" tests="2" skipped="0" failures="0" errors="0"/></testsuites>'})
    assert result.tests_passed and result.test_count==2


def test_unrelated_executed_class_does_not_cover_required_test(tmp_path):
    result=validate(tmp_path,{'TEST-example.OtherTest.xml':'<testsuite tests="1"><testcase classname="example.OtherTest" name="runs"/></testsuite>'})
    assert not result.tests_passed and any('Required behavior tests' in issue for issue in result.issues)


def test_repeated_case_names_are_executions_not_duplicate_reports(tmp_path):
    case='<testcase classname="example.OuterTest" name="repeat"/>'
    result=validate(tmp_path,{'TEST-example.OuterTest.xml':'<testsuite tests="2">'+case+case+'</testsuite>'})
    assert result.tests_passed and result.test_count==2
