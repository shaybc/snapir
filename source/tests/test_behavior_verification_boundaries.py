"""Locate real unit entry methods without executing originals or claiming equivalence."""

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from runtime.java_toolchain import run_java
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.java_tool import default_tool_path
from tools.maven_dependency_tools.command import maven_executable


@pytest.fixture(scope='module')
def boundary_tool():
    pom = Path(__file__).resolve().parents[1] / 'behavior-verification-java/pom.xml'
    result = run_java([maven_executable(), '-q', '--offline', '-f', str(pom), 'package'],
                      capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert default_tool_path().is_file()
    return default_tool_path()


def source(identity, content):
    return dict(identity=identity, content=content, content_hash=hashlib.sha256(content.encode()).hexdigest())


def unit(kind='configured_step', name='example.Work', sources=None):
    configuration = dict(attributes=dict(implClass=name)) if kind == 'configured_step' else dict(
        tag='fmtDef', definition_id='format', java_class=None, attributes=dict(id='Request'), children=[dict(
            tag='CCXML', java_class=name, decorators=[dict(java_class='example.Decorator')], children=[])])
    return dict(unit_id='unit-' + kind, fingerprint='original-fingerprint', operation_identity='original-operation',
        kind=kind, effective_configuration=configuration, configuration_xml='<original/>',
        referenced_definitions=[], sources=sources or [source('work',
            'package example; public class Work { public int execute() { return 0; } }')])


def prepared(*units):
    return dict(run_id='original-run', operations={'XML/Flow': dict(status='prepared', units=list(units))})


def first(report):
    return next(iter(report['boundaries'].values()))


def test_overloads_annotations_and_method_lines_are_source_bound(boundary_tool):
    text = '''package example;
public class Work {
    public int execute(String ignored) { return 99; }
    // No annotation or comment should be mistaken for a method.
    @Deprecated
    public int execute() {
        return 7;
    }
}
'''
    original = prepared(unit(sources=[source('original-work', text)]))
    original['operations']['XML/Flow']['behavior_request'] = dict(java_origins=[dict(
        status='verified_source', definition_id='original-work', source_file='original/Work.java')])
    saved = deepcopy(original)
    report = build_boundary_report(original, tool_jar=boundary_tool)
    entry = first(report)
    assert report['counts'] == dict(total=1, identified=1, incomplete=0)
    assert entry['legacy_method']['signature'] == 'example.Work.execute()'
    assert entry['legacy_method']['source_identity'] == 'original-work'
    assert entry['legacy_method']['source_file'] == 'original/Work.java'
    assert entry['legacy_method']['source_hash'] == source('original-work', text)['content_hash']
    assert entry['legacy_method']['start_line'] == 5
    assert entry['legacy_method']['end_line'] == 8
    assert entry['legacy_method']['excerpt'] in text
    assert entry['verification_status'] == report['verification_status'] == 'not_run'
    assert not report['acceptance_gate_enabled']
    assert original == saved


def test_inherited_implementation_points_to_parent_source(boundary_tool):
    value = unit(name='example.Child', sources=[
        source('child', 'package example; public class Child extends Parent {}'),
        source('parent', 'package example; public class Parent { public int execute() { return 1; } }')])
    entry = first(build_boundary_report(prepared(value), tool_jar=boundary_tool))
    assert entry['analysis_status'] == 'identified', entry['issues']
    assert entry['legacy_method']['implementation_class'] == 'example.Child'
    assert entry['legacy_method']['declaring_class'] == 'example.Parent'
    assert entry['legacy_method']['source_identity'] == 'parent'


def test_format_directions_select_exact_framework_signatures(boundary_tool):
    sources = [source('context', 'package com.ibm.dse.base; public class Context {}'), source('formatter', '''
package example;
import com.ibm.dse.base.Context;
public class Formatter {
    public String format(Context context) { return "<Value/>"; }
    public String format(Object unrelated) { return "wrong"; }
    public void unformat(String xml, Context context) { }
    public void unformat(String xml, Object unrelated) { }
}''')]
    request = unit('request_unformat', 'example.Formatter', sources)
    response = unit('response_format', 'example.Formatter', sources)
    report = build_boundary_report(prepared(request, response), tool_jar=boundary_tool)
    assert report['counts']['identified'] == 2, report
    for entry in report['boundaries'].values():
        assert 'com.ibm.dse.base.Context' in entry['legacy_method']['signature']
        assert entry['setup_class_roots'] == ['example.Decorator', 'example.Formatter']
        assert {'context_writes', 'context_removals', 'exceptions', 'external_calls'} <= set(entry['observable_results'])
        assert {'clock', 'random_seed', 'initial_settings', 'external_responses'} <= set(entry['inputs'])
    assert first(report)['implementation_class'] == 'example.Formatter'


@pytest.mark.parametrize('text', [
    'package example; public class Work { public static int execute() { return 1; } }',
    'package example; public class Work { public int execute(int ignored) { return 1; } }',
    'package example; public abstract class Work { public abstract int execute(); }',
    'package example; public class Work { public int execute() { invalid Java } }',
    'package example; public class Work extends Unavailable {}',
])
def test_missing_invalid_or_noninstance_entries_stay_incomplete(boundary_tool, text):
    report = build_boundary_report(prepared(unit(sources=[source('work', text)])), tool_jar=boundary_tool)
    entry = first(report)
    assert entry['analysis_status'] == 'verification_incomplete'
    assert entry['issues']
    assert entry['legacy_method'] is None
    assert report['verification_status'] == 'not_run'


def test_analysis_does_not_run_static_initializers(boundary_tool, tmp_path):
    marker = tmp_path / 'must-not-exist'
    literal = str(marker).replace('\\', '\\\\')
    text = ('package example; public class Work { static { '
            'try { java.nio.file.Files.createFile(java.nio.file.Path.of("' + literal + '")); } '
            'catch (Exception e) { throw new RuntimeException(e); } } public int execute() { return 0; } }')
    report = build_boundary_report(prepared(unit(sources=[source('work', text)])), tool_jar=boundary_tool)
    assert first(report)['analysis_status'] == 'identified'
    assert not marker.exists()


def test_missing_tool_preserves_preparation_and_reports_incomplete(tmp_path):
    preparation = prepared(unit())
    saved = deepcopy(preparation)
    report = build_boundary_report(preparation, tool_jar=tmp_path / 'absent.jar')
    assert preparation == saved
    assert first(report)['analysis_status'] == 'verification_incomplete'
    assert 'Build the converter analysis tool' in first(report)['issues'][0]


def test_default_step_mapping_and_referenced_format_are_explicit():
    value = unit()
    value['effective_configuration']['attributes'] = {}
    assert boundary_contract(value).issues
    assert boundary_contract(value, {'opStep': 'example.Work'}).implementation_class == 'example.Work'
    value = unit('request_unformat', 'example.Formatter')
    body = value['effective_configuration']
    value['effective_configuration'] = dict(tag='refFmt', reference_definition_id='format')
    value['referenced_definitions'] = [body]
    assert boundary_contract(value).implementation_class == 'example.Formatter'
    value['referenced_definitions'] = []
    assert boundary_contract(value).issues


def test_effective_configuration_and_evidence_revisions_change_boundaries():
    original = unit()
    changed = deepcopy(original)
    changed['effective_configuration']['attributes']['limit'] = '10'
    assert boundary_contract(original).configuration_hash != boundary_contract(changed).configuration_hash
    changed = deepcopy(original)
    changed['sources'] = [source('work', original['sources'][0]['content'].replace('return 0;', 'return 1;'))]
    assert boundary_contract(original).source_manifest_hash != boundary_contract(changed).source_manifest_hash


@pytest.mark.parametrize('version', [21, 25])
def test_tool_runs_on_supported_java_profiles(boundary_tool, version):
    from types import SimpleNamespace
    from runtime.java_toolchain import java_scope, resolve_java_home
    try:
        home = resolve_java_home(version)
    except ValueError:
        pytest.skip('This host has no Java ' + str(version))
    with java_scope(SimpleNamespace(java_version=version, java_home=home)):
        report = build_boundary_report(prepared(unit()), tool_jar=boundary_tool)
    assert report['counts']['identified'] == 1, report
