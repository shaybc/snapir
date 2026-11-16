"""Exercise real project-specific JAR resolution without executing library code."""

from copy import deepcopy
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from models.java_classpath_index import JavaClasspathIndex
from models.project_classpath import ProjectClasspath, ProjectClasspathEntry
from runtime.java_toolchain import run_java, java_environment
from test_behavior_verification_boundaries import boundary_tool, unit, source
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_classpath import project_context
from tools.behavior_verification.boundary_contracts import boundary_contract


def archive(folder, files):
    """Compile a real dependency JAR using the supported JDK and source-only fixtures."""
    java = folder / 'java'
    classes = folder / 'classes'
    classes.mkdir(parents=True)
    paths = []
    for name, text in files.items():
        path = java / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        paths.append(str(path))
    result = run_java(['javac', '--release', '21', '-d', str(classes), *paths],
        env=java_environment(25), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    path = folder / 'dependency with spaces.jar'
    with ZipFile(path, 'w') as jar:
        for compiled in classes.rglob('*.class'):
            jar.write(compiled, compiled.relative_to(classes).as_posix())
    return path


def view(project, paths, roots=()):
    entries = [ProjectClasspathEntry(kind='source', path=str(root), rank=[number]) for number, root in enumerate(roots)]
    entries += [ProjectClasspathEntry(kind='library', path=str(path), rank=[len(entries) + number]) for number, path in enumerate(paths)]
    return ProjectClasspath(directory=project, entries=entries)


def operation(value, owners):
    origins = [dict(definition_id=item['identity'], status='verified_source', fqcn=name,
        source_project=project, source_file=str(path), source_hash=item['content_hash'])
        for item, (name, project, path) in zip(value['sources'], owners)]
    return dict(units=[value], behavior_request=dict(java_origins=origins))


@pytest.fixture
def context_jar(tmp_path):
    return archive(tmp_path / 'context', {'com/ibm/api/Context.java': 'package com.ibm.api; public class Context {}'})


@pytest.mark.parametrize('known_order', [True, False])
def test_parameter_type_supplied_only_by_project_jar_is_resolved(tmp_path, boundary_tool, context_jar, known_order):
    text = 'package example; public class Formatter { public String format(com.ibm.api.Context context){ return ""; } }'
    value = unit('response_format', 'example.Formatter', [source('formatter', text)])
    value['effective_configuration']['children'][0]['decorators'] = []
    preparation = dict(operations={'BANK/Op': operation(value, [('example.Formatter', 'BANK', tmp_path / 'BANK/Formatter.java')])})
    index = JavaClasspathIndex(project_classpaths={'BANK': view('BANK', [context_jar])})
    index.project_classpaths['BANK'].entries[0].order_known = known_order
    before = deepcopy(preparation)
    report = build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index)
    boundary = next(iter(report['boundaries'].values()))
    assert report['counts']['identified'] == 1, boundary['issues']
    assert boundary['legacy_method']['signature'] == 'example.Formatter.format(com.ibm.api.Context)'
    assert preparation == before


def test_supplied_enum_remains_resolvable_in_project_context(tmp_path, boundary_tool, context_jar):
    text = 'package example; public class Formatter { public String format(com.ibm.api.Context context){ apply(Mode.ONE); return ""; } public void apply(Mode mode){} }'
    value = unit('response_format', 'example.Formatter', [source('formatter', text),
        source('mode', 'package example; public enum Mode { ONE }')])
    value['effective_configuration']['children'][0]['decorators'] = []
    preparation = dict(operations={'BANK/Op': operation(value, [('example.Formatter', 'BANK', tmp_path / 'Formatter.java'),
        ('example.Mode', 'BANK', tmp_path / 'Mode.java')])})
    index = JavaClasspathIndex(project_classpaths={'BANK': view('BANK', [context_jar])})
    report = build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index)
    assert report['counts']['identified'] == 1, report
    assert 'example.Formatter.apply(example.Mode)' in json.dumps(report)


def test_opposite_jar_order_stays_separate_for_identical_source_scopes(tmp_path, boundary_tool):
    good = archive(tmp_path / 'good', {'vendor/Base.java': 'package vendor; public class Base { public int execute(){ return 0; } }'})
    bad = archive(tmp_path / 'bad', {'vendor/Base.java': 'package vendor; public class Base { public int execute(int ignored){ return 0; } }'})
    operations = {}
    for project in ('A', 'B'):
        value = unit(sources=[source('work', 'package example; public class Work extends vendor.Base {}')])
        value['unit_id'] = project
        operations[project + '/Op'] = operation(value, [('example.Work', project, tmp_path / project / 'Work.java')])
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [good, bad]), 'B': view('B', [bad, good])})
    for project in index.project_classpaths.values():
        for entry in project.entries:
            entry.rank = [0]
            entry.order_known = False
    report = build_boundary_report(dict(operations=operations), tool_jar=boundary_tool, classpath_index=index)
    assert any('no supplied Java source' in issue for issue in report['boundaries']['A']['issues'])
    assert any('matches=0' in issue for issue in report['boundaries']['B']['issues'])
    # Resolving a binary method must not invent a supplied source body for conversion.
    assert report['counts']['identified'] == 0


def test_referenced_source_uses_its_own_nonexported_library(tmp_path, boundary_tool, context_jar):
    value = unit('response_format', 'example.Work', [
        source('work', 'package example; public class Work extends helper.Helper {}'),
        source('helper', 'package helper; public class Helper { public String format(com.ibm.api.Context context){ return ""; } }')])
    value['effective_configuration']['children'][0]['decorators'] = []
    a, b = tmp_path / 'A/src', tmp_path / 'B/src'
    preparation = dict(operations={'A/Op': operation(value, [('example.Work', 'A', a / 'Work.java'), ('helper.Helper', 'B', b / 'Helper.java')])})
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [], [a, b]), 'B': view('B', [context_jar], [b])})
    context = project_context(value, boundary_contract(value), preparation['operations']['A/Op']['behavior_request']['java_origins'], index)
    assert context['projects']['A']['libraries'] == []
    report = build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index)
    boundary = next(iter(report['boundaries'].values()))
    assert report['counts']['identified'] == 1, boundary['issues']
    assert boundary['legacy_method']['declaring_class'] == 'helper.Helper'
    # B's private JAR must not become directly visible to A's own declaration.
    changed = deepcopy(value)
    changed['sources'][0] = source('work', 'package example; public class Work extends helper.Helper { public String format(com.ibm.api.Context context){ return ""; } }')
    hidden = build_boundary_report(dict(operations={'A/Op': operation(changed,
        [('example.Work', 'A', a / 'Work.java'), ('helper.Helper', 'B', b / 'Helper.java')])}),
        tool_jar=boundary_tool, classpath_index=index)
    assert hidden['counts']['identified'] == 0


@pytest.mark.parametrize('problem', ['missing', 'corrupt', 'relative', 'unknown-owner', 'unreadable'])
def test_invalid_project_evidence_is_rejected_before_analyzer(tmp_path, context_jar, problem, monkeypatch):
    value = unit()
    metadata = operation(value, [('example.Work', 'A', tmp_path / 'Work.java')])
    path = context_jar
    if problem == 'missing': path = tmp_path / 'absent.jar'
    if problem == 'corrupt':
        path = tmp_path / 'corrupt.jar'
        path.write_bytes(b'not a jar')
    if problem == 'relative': path = Path('relative.jar')
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [path])})
    if problem == 'unknown-owner': metadata['behavior_request']['java_origins'][0].pop('source_project')
    if problem == 'unreadable':
        def denied(*args): raise PermissionError('unreadable JAR')
        monkeypatch.setattr('tools.behavior_verification.boundary_classpath.ZipFile', denied)
    report = build_boundary_report(dict(operations={'A/Op': metadata}), tool_jar=tmp_path / 'no-tool.jar', classpath_index=index)
    issues = next(iter(report['boundaries'].values()))['issues']
    assert issues and not any('Build the converter analysis tool' in issue for issue in issues)


def test_archive_changes_are_detected_on_the_same_verified_index(tmp_path, context_jar):
    value = unit()
    metadata = operation(value, [('example.Work', 'A', tmp_path / 'Work.java')])
    origins = metadata['behavior_request']['java_origins']
    index = JavaClasspathIndex(project_classpaths={'A': view('A', [context_jar])})
    project_context(value, boundary_contract(value), origins, index)
    with context_jar.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='Archive changed'):
        project_context(value, boundary_contract(value), origins, index)


def test_runtime_report_uses_current_verified_paths_without_intake(tmp_path, boundary_tool, context_jar, monkeypatch):
    from types import SimpleNamespace
    from runtime.behavior_verification_boundaries import write_boundary_report
    text = 'package example; public class Formatter { public String format(com.ibm.api.Context context){ return ""; } }'
    value = unit('response_format', 'example.Formatter', [source('formatter', text)])
    value['effective_configuration']['children'][0]['decorators'] = []
    preparation = dict(operations={'BANK/Op': operation(value, [('example.Formatter', 'BANK', tmp_path / 'BANK/Formatter.java')])},
        reused_contexts=['BANK/Op'])
    index = JavaClasspathIndex(project_classpaths={'BANK': view('BANK', [context_jar])})
    access = SimpleNamespace(operation=lambda *args: SimpleNamespace(channel='BANK'),
                             channel_evidence=lambda context: {'markdown': ''})
    monkeypatch.setattr('runtime.behavior_verification_boundaries.ScopedVaultAccess', lambda *args: access)
    monkeypatch.setattr('runtime.behavior_verification_boundaries.parse_channel_note', lambda *args: [])
    def verified(root, jars, variables, **kwargs):
        assert root == str(tmp_path) and kwargs['profile'] is profile
        return index
    monkeypatch.setattr('tools.source_discovery_tools.classpath_scope.discover_conversion_classpath', verified)
    def forbidden(*args, **kwargs): pytest.fail('Boundary analysis repeated intake or source discovery')
    monkeypatch.setattr('tools.composer_mapper_tools.vault_importer.import_vault', forbidden)
    monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch', forbidden)
    config = SimpleNamespace(run_id='saved', source_root=str(tmp_path))
    profile = SimpleNamespace(classpath_jars=[], eclipse_classpath_variables={})
    report = write_boundary_report(None, config, preparation, tmp_path / 'run', profile=profile)
    assert report['counts']['identified'] == 1, report
    context = next(iter(report['analysis_classpaths'].values()))
    assert context['projects']['BANK']['libraries'][0]['path'] == str(context_jar.resolve())


def test_jar_revision_changes_analysis_identity(tmp_path, boundary_tool, context_jar):
    value = unit(sources=[source('work', 'package example; public class Work { public int execute(){ return 0; } }')])
    preparation = dict(operations={'BANK/Op': operation(value, [('example.Work', 'BANK', tmp_path / 'Work.java')])})
    def analyze():
        index = JavaClasspathIndex(project_classpaths={'BANK': view('BANK', [context_jar])})
        return build_boundary_report(preparation, tool_jar=boundary_tool, classpath_index=index)
    first = analyze()
    with ZipFile(context_jar, 'a') as jar:
        jar.writestr('new-revision.txt', 'different archive bytes')
    second = analyze()
    assert first['counts']['identified'] == second['counts']['identified'] == 1
    assert first['analysis_tool_hash'] == second['analysis_tool_hash']
    assert first['analysis_classpath_hash'] != second['analysis_classpath_hash']


@pytest.mark.parametrize('problem', ['old-tool', 'changed-library'])
def test_analyzer_protocol_and_inflight_archive_changes_are_rejected(tmp_path, boundary_tool, context_jar, monkeypatch, problem):
    from types import SimpleNamespace
    from xml.etree import ElementTree
    from tools.behavior_verification.java_tool import analyze_entries
    value = unit()
    metadata = operation(value, [('example.Work', 'BANK', tmp_path / 'Work.java')])
    boundary = boundary_contract(value)
    index = JavaClasspathIndex(project_classpaths={'BANK': view('BANK', [context_jar])})
    context = project_context(value, boundary, metadata['behavior_request']['java_origins'], index)
    def analyze(command, **kwargs):
        manifest = ElementTree.parse(command[-2]).getroot()
        library = manifest.find('scope/project/library')
        assert library.get('path') == str(context_jar.resolve())
        if problem == 'changed-library':
            with context_jar.open('ab') as stream: stream.write(b'changed during analysis')
        Path(command[-1]).write_text('<analysis/>')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('tools.behavior_verification.java_tool.run_java', analyze)
    with pytest.raises(ValueError, match='lacks project classpath support' if problem == 'old-tool' else 'JAR changed'):
        analyze_entries({'scope': dict(sources=value['sources'], boundaries=[boundary], classpath=context)}, boundary_tool)
