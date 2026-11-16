"""Recognize listed binary ancestors without inventing source or changing entry rules."""

from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from test_behavior_verification_boundaries import boundary_tool, unit, source, prepared, first
from test_boundary_project_classpath import archive, operation, view
from models.java_classpath_index import JavaClasspathIndex
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.framework_jars import framework_libraries


@pytest.fixture
def framework(tmp_path):
    return archive(tmp_path / 'framework', {
        'com/ibm/api/Context.java': 'package com.ibm.api; public class Context {}',
        'vendor/Base.java': '''package vendor; public class Base {
            static { if (true) throw new IllegalStateException("must never execute during analysis"); }
            public String format(com.ibm.api.Context context) { return "framework"; }
        }''',
        'vendor/Middle.java': 'package vendor; public class Middle extends Base {}'})


def formatter(override=False):
    body = 'public String format(com.ibm.api.Context context) { return "application"; }' if override else ''
    value = unit('response_format', 'example.Formatter', [source('formatter',
        'package example; public class Formatter extends vendor.Middle {' + body + '}')])
    value['effective_configuration']['children'][0]['decorators'] = []
    return value


def test_listed_inherited_binary_method_needs_no_source(boundary_tool, framework):
    report = build_boundary_report(prepared(formatter()), tool_jar=boundary_tool, framework_jars=[framework])
    entry = first(report)
    assert entry['analysis_status'] == 'identified', entry['issues']
    method = entry['framework_method']
    assert method['implementation_class'] == 'example.Formatter'
    assert method['declaring_class'] == 'vendor.Base'
    assert method['signature'] == 'vendor.Base.format(com.ibm.api.Context)'
    assert method['jar_path'] == str(framework.resolve())
    assert method['jar_sha256'] == framework_libraries([framework])[0]['sha256']
    assert method['source_required'] is method['conversion_target'] is False
    assert entry['legacy_method'] is entry['reachable_slice'] is entry['parser_checklist'] is None
    assert entry['verification_status'] == 'not_run'
    assert not report['acceptance_gate_enabled']


def test_source_override_remains_application_code(boundary_tool, framework):
    entry = first(build_boundary_report(prepared(formatter(True)), tool_jar=boundary_tool, framework_jars=[framework]))
    assert entry['analysis_status'] == 'identified', entry['issues']
    assert entry['legacy_method']['declaring_class'] == 'example.Formatter'
    assert 'framework_method' not in entry


def test_unlisted_binary_still_requires_source(tmp_path, boundary_tool, framework):
    value = formatter()
    preparation = dict(operations={'A/Op': operation(value, [('example.Formatter', 'A', tmp_path / 'Formatter.java')])})
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [framework])})
    entry = first(build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index))
    assert entry['analysis_status'] == 'verification_incomplete'
    assert any('no supplied Java source' in issue for issue in entry['issues'])
    listed = first(build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index, framework_jars=[framework]))
    assert listed['analysis_status'] == 'identified', listed['issues']


def test_configured_jars_are_available_in_project_analysis(tmp_path, boundary_tool, framework):
    value = formatter()
    preparation = dict(operations={'A/Op': operation(value, [('example.Formatter', 'A', tmp_path / 'Formatter.java')])})
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [])})
    entry = first(build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index, framework_jars=[framework]))
    assert entry['analysis_status'] == 'identified', entry['issues']
    assert entry['framework_method']['declaring_class'] == 'vendor.Base'


def test_framework_methods_do_not_supply_an_unrelated_class_boundary(boundary_tool, framework):
    value = formatter()
    value['sources'] = [source('formatter', 'package example; public class Formatter {}')]
    entry = first(build_boundary_report(prepared(value), tool_jar=boundary_tool, framework_jars=[framework]))
    assert entry['analysis_status'] == 'verification_incomplete'
    assert 'framework_method' not in entry
    assert any('matches=0' in issue for issue in entry['issues'])


def test_abstract_framework_entry_stays_incomplete(tmp_path, boundary_tool):
    jar = archive(tmp_path / 'abstract', {'vendor/Base.java':
        'package vendor; public abstract class Base { public abstract int execute(); }'})
    value = unit(sources=[source('work', 'package example; public abstract class Work extends vendor.Base {}')])
    entry = first(build_boundary_report(prepared(value), tool_jar=boundary_tool, framework_jars=[jar]))
    assert entry['analysis_status'] == 'verification_incomplete'
    assert any('no executable body' in issue for issue in entry['issues'])


def test_duplicate_framework_class_is_not_accepted(tmp_path, boundary_tool, framework):
    duplicate = tmp_path / 'duplicate.jar'
    duplicate.write_bytes(framework.read_bytes())
    entry = first(build_boundary_report(prepared(formatter()), tool_jar=boundary_tool, framework_jars=[framework, duplicate]))
    assert entry['analysis_status'] == 'verification_incomplete'
    assert any('multiple configured JARs' in issue for issue in entry['issues'])


def test_framework_revision_changes_reuse_identity(boundary_tool, framework):
    def analyze():
        return build_boundary_report(prepared(formatter()), tool_jar=boundary_tool, framework_jars=[framework])
    before = analyze()
    with ZipFile(framework, 'a') as jar:
        jar.writestr('revision.txt', 'changed')
    after = analyze()
    assert before['analysis_classpath_hash'] != after['analysis_classpath_hash']


def test_generation_retains_application_sources_without_claiming_framework_body(boundary_tool, framework, monkeypatch):
    from runtime.behavior_conversion.verification_request import attach_verification
    report = build_boundary_report(prepared(formatter()), tool_jar=boundary_tool, framework_jars=[framework])
    monkeypatch.setattr('runtime.behavior_conversion.verification_request.build_boundary_report', lambda *args, **kwargs: report)
    payload, boundary, original = attach_verification(formatter(), collect_facts=False, framework_jars=[framework])
    assert payload['slice_sources'][0]['content'] == original['sources'][0]['content']
    assert payload['slice_sources'][0]['kind'] == 'supplied_application_source'
    assert boundary.reachable_slice is None
    assert payload['boundary']['framework_method']['declaring_class'] == 'vendor.Base'
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    with pytest.raises(VerificationIncomplete):
        attach_verification(formatter(), collect_facts=True, framework_jars=[framework])


def test_original_tests_include_framework_jars_without_reordering():
    from runtime.behavior_conversion.original_classpath import original_classpath
    profile = SimpleNamespace(classpath_jars=['first.jar', 'framework.jar'], framework_jars=['framework.jar', 'second.jar'])
    assert original_classpath(profile, {}) == ['first.jar', 'framework.jar', 'second.jar']


def test_framework_profile_paths_and_saved_defaults(tmp_path):
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.configuration import load_configuration
    (tmp_path / 'src').mkdir()
    (tmp_path / 'mapper.jar').touch()
    profile = tmp_path / 'profile.yaml'
    profile.write_text('source_root: src\nmapper_jar: mapper.jar\nframework_jars:\n  - lib/base.jar\n  - lib/runtime.jar\n')
    configured = load_configuration(profile)
    assert configured.framework_jars == [str((tmp_path / 'lib/base.jar').resolve()), str((tmp_path / 'lib/runtime.jar').resolve())]
    assert PipelineConfiguration.model_validate_json(configured.model_dump_json()).framework_jars == configured.framework_jars
    assert PipelineConfiguration().framework_jars == []


@pytest.mark.parametrize('own', [True, False])
def test_component_request_does_not_borrow_framework_boundary(tmp_path, own):
    from runtime.component_conversion.requests import build_component_request
    from models.component_conversion_plan import ComponentConversionPlan
    from models.component_conversion_group import ComponentConversionGroup
    from models.planned_conversion_component import PlannedConversionComponent
    from models.pipeline_configuration import PipelineConfiguration
    value = formatter()['sources'][0]
    path = tmp_path / 'Formatter.java'
    path.write_text(value['content'], encoding='utf-8')
    group = ComponentConversionGroup(group_id='group', members=['formatter'], reason='test')
    node = PlannedConversionComponent(component_id='formatter', kind='java_implementation', label='example.Formatter',
        status='source_recorded', roles=['format_leaf'], unit_ids=['unit'],
        provenance=dict(definition_id=value['identity'], source_hash=value['content_hash'], source_file=str(path)))
    plan = ComponentConversionPlan(components={'formatter': node}, groups=[group])
    profile = PipelineConfiguration()
    profile.executable_verification.mode = 'test_based_v1'
    owner = node.label if own else 'unrelated.ContainerFormat'
    boundaries = dict(analysis_tool_hash='test', boundaries={'unit': dict(framework_method=dict(
        implementation_class=owner, signature='vendor.Base.format(com.ibm.api.Context)'))})
    if not own:
        with pytest.raises(ValueError, match='no parser-backed entry points'):
            build_component_request(plan, group, boundaries, [], profile)
        return
    request, _ = build_component_request(plan, group, boundaries, [], profile, check_budget=False)
    assert request['framework_methods']['formatter'][0]['implementation_class'] == node.label
    assert request['source_entry_points']['formatter'] == ['vendor.Base.format(com.ibm.api.Context)']


@pytest.mark.parametrize('content', [None, b'invalid archive'])
def test_missing_or_invalid_framework_jar_is_explicit(tmp_path, content):
    jar = tmp_path / 'bad.jar'
    if content is not None:
        jar.write_bytes(content)
    with pytest.raises(ValueError, match='Framework JAR'):
        framework_libraries([jar])
