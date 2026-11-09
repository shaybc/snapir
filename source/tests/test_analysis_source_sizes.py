"""Keep offline preparation independent of the AI conversion source-size guard."""

import hashlib
from pathlib import Path
from xml.etree import ElementTree

import pytest

from models.conversion_component import ConversionComponent
from models.java_classpath_index import JavaClasspathIndex
from models.java_source_index import JavaSourceIndex
from tests.test_scoped_closure import import_workspace, workspace
from tests.test_scoped_vault_identity import scoped_mapper
from tests.indexed_mapper_fixture import indexed_mapper_jar, generate
from tests.test_scoped_workflow import settings, prepare
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.java_analysis_tools.java_text import read_java_text
from tools.conversion_tools.java_dependency_readiness import check_java_dependencies


def large_sources(root, *, include_helper=True):
    """Exercise large roots, format implementations and a transitive helper."""
    padding = '/*' + ('large source evidence ' * 2000) + '*/\r\n'
    sources = {
        'Work': 'import example.Helper; public class Work { private Helper helper; }' if include_helper else 'public class Work {}',
        'Helper': 'public class Helper {}',
        'Field': 'public class Field {}',
    }
    for name, body in sources.items():
        (root / 'src/example' / (name + '.java')).write_bytes(('package example;\r\n' + padding + body).encode())


def test_large_sources_prepare_and_restore_without_weakening_conversion_guard(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=lambda root: large_sources(root, include_helper=False))
    try:
        config, profile = settings(root, vault)
        original = {str(path): path.read_bytes() for path in (root / 'src/example').glob('*.java')}
        report = prepare(conn, config, profile)
        assert all(item['status'] == 'prepared' for item in report['operations'].values()), {
            name: item.get('blockers') for name, item in report['operations'].items()}
        units = report['operations']['SME/Flow']['units']
        text = (root / 'src/example/Work.java').read_bytes().decode()
        assert len(text) > 32000 and '\r\n' in text
        assert any(source['content'] == text for unit in units for source in unit['sources'])
        again = prepare(conn, config, profile)
        assert again['operations']['SME/Flow']['units'] == units
        with pytest.raises(ValueError, match='MAX_SOURCE_CHARS_PER_CONVERSION'):
            read_java_source(str(root / 'src/example/Work.java'))
        assert all(Path(path).read_bytes() == data for path, data in original.items())
    finally:
        conn.close()


def test_large_indexed_source_reuses_ast_without_java_reparsing(tmp_path, indexed_mapper_jar, monkeypatch):
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.pipeline_runner import run_pipeline
    from runtime.java_toolchain import resolve_java_home
    from runtime.workspace_paths import run_report_path
    import json
    root, vault = tmp_path / 'source', tmp_path / 'map'
    workspace(root)
    large_sources(root)
    generate(indexed_mapper_jar, root, vault)
    def forbidden(*args, **kwargs):
        pytest.fail('Indexed preparation reparsed Java or called AI')
    monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch', forbidden)
    monkeypatch.setattr('runtime.behavior_conversion.runner.generate', forbidden)
    profile = PipelineConfiguration(source_root=str(root), existing_composer_map=str(vault), mapper_analysis_format='indexed-v1',
        mapper_vault_layout='scoped', source_workspace_id='bank', channels=['XML'], include_operations=['Flow'],
        output_root=str(tmp_path / 'runs'), java_version=25, java_home=resolve_java_home(25), model_provider='mock',
        scoped_native_mode='component_first_v1', conversion_strategy='behavior_units', plan_approval_policy='human',
        executable_verification=dict(mode='test_based_v1'), test_preparation=dict(mode='ai_shared_fixtures_v1'))
    directory = run_pipeline(profile, 'large-sources')
    report = json.loads(run_report_path(directory, 'scoped_workflow_preparation.json').read_text())
    assert report['operations']['XML/Flow']['status'] == 'prepared', report


@pytest.mark.parametrize('changed', [False, True])
def test_recursive_dependency_read_accepts_large_helper_and_keeps_revision_check(tmp_path, changed):
    root, helper = tmp_path / 'Work.java', tmp_path / 'Helper.java'
    root.write_text('package example; class Work { Helper helper; }')
    helper.write_text('package example; /*' + 'evidence ' * 5000 + '*/ class Helper {}')
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (root, helper)}
    if changed:
        helper.write_text(helper.read_text() + '\n// changed')
    sources = JavaSourceIndex(workspace_root=str(tmp_path), classes={'example.Work': [str(root)], 'example.Helper': [str(helper)]},
        class_projects={str(root): '.', str(helper): '.'}, source_roots={'.': [str(tmp_path)]})
    component = ConversionComponent(kind='ibm_java', logical_id='example.Work', source_file=str(root),
        source_hash=hashes[str(root)], source_content=root.read_text(), origin='test')
    def parser(paths):
        analysis = ElementTree.Element('analysis')
        for path in paths:
            document = ElementTree.SubElement(analysis, 'source', path=str(path), package='example')
            if path == str(root):
                ElementTree.SubElement(document, 'reference', name='Helper', kind='type')
        return analysis
    components, issues = check_java_dependencies([component], sources, JavaClasspathIndex(), hashes, source_parser=parser)
    if changed:
        assert any('changed since intake' in issue.detail for issue in issues)
    else:
        assert not issues
        assert next(item for item in components if item.logical_id == 'example.Helper').source_content == helper.read_text()


def test_analysis_read_keeps_hash_verification_and_decoding(tmp_path):
    path = tmp_path / 'Large.java'
    raw = ('class Large { /*' + 'שלום ' * 9000 + '*/ }\r\n').encode('cp1255')
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    assert read_java_text(path, expected_hash=digest, preserve_line_endings=True).endswith('\r\n')
    path.write_bytes(raw + b' ')
    with pytest.raises(ValueError, match='revision differs'):
        read_java_text(path, expected_hash=digest)


def test_original_format_dependency_discovery_keeps_its_own_byte_budget(tmp_path):
    from models.boundary_harness_binding import BoundaryHarnessBinding
    from models.composer_unit_specification import ComposerUnitSpecification
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.composer_units.discovery import discover
    from runtime.composer_units.selection import standalone
    (tmp_path / 'src/example').mkdir(parents=True)
    large_sources(tmp_path)
    profile = PipelineConfiguration(source_root=str(tmp_path), scoped_java_project='.')
    spec = ComposerUnitSpecification(unit=standalone('example.Field'), framework=BoundaryHarnessBinding(
        adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter', context_class='example.Helper', tag_class='example.Work'))
    resolved, _ = discover(spec, profile)
    assert all(len(source['content']) > 32000 for source in resolved['sources'])
    with pytest.raises(ValueError, match='dependency limit exceeded'):
        discover(spec.model_copy(update={'max_source_bytes': 100}), profile)
