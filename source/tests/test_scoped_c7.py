"""Verify source-backed C7 preparation fixes without enabling native conversion."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.java_classpath_index import JavaClasspathIndex
from models.java_source_index import JavaSourceIndex
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import resolve_java_home
from runtime.workspace_paths import run_report_path
from tools.conversion_tools.scoped_closure.platform_imports import verified_platform_wildcard
from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project
from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
from test_scoped_vault_identity import scoped_mapper


def test_channel_project_override_is_exact_and_preserves_fallback():
    profile = PipelineConfiguration(scoped_java_project='fallback', scoped_java_projects={'IVR': 'ivr'})
    assert scoped_source_project(profile, 'IVR') == 'ivr'
    assert scoped_source_project(profile, 'ivr') == 'fallback'
    assert scoped_source_project(SimpleNamespace(), 'SME') is None
    changed = profile.model_copy(update={'scoped_java_projects': {'IVR': 'other'}})
    assert conversion_policy(profile) != conversion_policy(changed)
    assert PipelineConfiguration.model_validate_json(profile.model_dump_json()).scoped_java_projects == {'IVR': 'ivr'}


@pytest.mark.parametrize('mapping', [{'': 'p'}, {'IVR': ''}, {'IVR': '  '}])
def test_empty_project_mapping_is_rejected(mapping):
    with pytest.raises(ValueError, match='nonblank'):
        PipelineConfiguration(scoped_java_projects=mapping)


@pytest.mark.parametrize('name,locations,source,expected', [
    ('java.sql.*', ['jdk:test'], False, True),
    ('java.sql.Connection', ['jdk:test'], False, False),
    ('java.missing.*', ['jdk:test'], False, False),
    ('java.sql.*', ['jar:test'], False, False),
    ('java.sql.*', ['jdk:test', 'jar:test'], False, False),
    ('java.sql.*', ['jdk:test'], True, False),
])
def test_platform_wildcard_requires_exact_jdk_package_without_competition(name, locations, source, expected):
    index = JavaSourceIndex(workspace_root='.', classes={'java.sql.Connection': ['source']} if source else {})
    classpath = JavaClasspathIndex(classes={'java.sql.Connection': locations})
    assert verified_platform_wildcard(name, index, classpath) is expected


def test_legacy_wildcard_classifier_is_unchanged(tmp_path):
    from tools.source_discovery_tools.dependencies import classify_java_imports
    source = tmp_path / 'Work.java'
    source.write_text('import java.sql.*;\nclass Work {}')
    result = classify_java_imports(str(source), JavaSourceIndex(workspace_root=str(tmp_path)),
        JavaClasspathIndex(classes={'java.sql.Connection': ['jdk:test']}))
    assert result[0]['kind'] == 'needs_review'


def test_dispatch_boundary_is_not_a_service_but_external_lookups_still_block(monkeypatch):
    from tools.conversion_tools.scoped_workflow import connections
    source = lambda identity: SimpleNamespace(identity=identity, content='getService("External")')
    unit = SimpleNamespace(operation_calls=[], sources=[source('dispatch'), source('external')],
        occurrence_id='one', configuration_xml='<opStep/>')
    closure = SimpleNamespace(calls=[{}], channel='IVR', operation_id='Flow', java_origins=[dict(
        definition_id='dispatch', fqcn='com.ibm.il.dse.cc.cut.CCComplexOpStep',
        status='verified_source', source_file='dispatcher.java')])
    monkeypatch.setattr(connections, 'discover_java_sources', lambda root: JavaSourceIndex(
        workspace_root='.', source_roots={'.': ['src']}))
    inspected = []
    def evidence(conn, config, channel, key, sources, *args, **kwargs):
        inspected.extend(sources)
        return [SimpleNamespace(issues=['Missing actual external service'])], None, None
    monkeypatch.setattr(connections, 'connection_evidence', evidence)
    with pytest.raises(ValueError, match='Missing actual external service'):
        connections.attach_scoped_connections(None, SimpleNamespace(source_root='.'), closure, unit,
            SimpleNamespace(scoped_java_project='.'), JavaClasspathIndex())
    assert inspected == ['external']
    assert [source.identity for source in unit.sources] == ['dispatch', 'external']


def test_jdk_wildcard_does_not_hide_an_unresolved_actual_type(tmp_path, scoped_mapper):
    from test_scoped_closure import import_workspace, build
    def change(root):
        (root / 'src/example/Work.java').write_text(
            'package example;\nimport java.sql.*;\npublic class Work { MissingType missing; }')
    conn, root, _ = import_workspace(tmp_path, scoped_mapper, change=change)
    try:
        closure = build(conn, root, java_project='.',
            classpath_index=JavaClasspathIndex(classes={'java.sql.Connection': ['jdk:test']}))
        assert closure.status == 'blocked'
        assert any('MissingType' in problem.detail for problem in closure.blocking_issues)
    finally:
        conn.close()


def test_fresh_bank_demo_all_ten_contexts_prepare_with_original_sources(tmp_path, scoped_mapper):
    from runtime.pipeline_runner import run_pipeline
    from runtime.checkpoints import resume_pipeline
    from runtime.configuration import load_configuration
    from tools.source_discovery_tools import discover_java_sources, resolve_indexed_source
    from tools.state_store_tools.db import get_connection
    try:
        home = resolve_java_home(25)
    except ValueError as exc:
        pytest.skip(str(exc))
    repository = Path(__file__).resolve().parents[2]
    root = tmp_path / 'workspace'
    shutil.copytree(repository / 'bank-demo/composer/Workspace', root)
    before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    jar = tmp_path / 'mapper.jar'
    subprocess.run([str(Path(home) / 'bin/jar'), '--create', '--file', str(jar), '--main-class',
        'il.co.dcd.composermapper.Main', '-C', str(scoped_mapper), '.'], check=True, capture_output=True)
    profile = load_configuration(repository / 'bank-demo/scoped_converter_validation.yaml')
    profile.source_root, profile.mapper_jar = str(root), str(jar)
    profile.output_root, profile.java_home = str(tmp_path / 'runs'), home
    profile.model_provider = 'mock'
    directory = run_pipeline(profile, 'c7-demo')
    resume_pipeline(profile.output_root, 'c7-demo')
    report = json.loads(run_report_path(directory, 'scoped_workflow_preparation.json').read_text())
    assert len(report['operations']) == 10
    assert all(op['status'] == 'prepared' for op in report['operations'].values()), {
        key: value['blockers'] for key, value in report['operations'].items() if value['blockers']}
    assert not report['conversion_enabled']
    manifest = json.loads((directory / 'vault/vault-manifest.json').read_text())
    assert not any('Ambiguous context' in str(issue) or 'ErrorBody' in str(issue) for issue in manifest.get('diagnostics', []))
    index = discover_java_sources(str(root))
    assert resolve_indexed_source(index, 'com.ibm.dse.base.Context', project='WSBCC_INTERNET')
    assert resolve_indexed_source(index, 'com.ibm.il.dse.operations.common.MapErrorByValueAlways', project='WSBCC_IVR')
    assert resolve_indexed_source(index, 'com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP', project='WSBCC_INTERNET') is None
    fraud = report['operations']['INTERNET/TransferFundsOp']
    assert any(unit.get('service_connections') for unit in fraud['units'])
    with get_connection(str(directory / 'state/migration.db')) as conn:
        closures = [json.loads(row[0]) for row in conn.execute('SELECT closure_json FROM scoped_operation_closures')]
    assert all(closure['status'] == 'evidence_ready' for closure in closures)
    assert not profile.external_dependencies, 'No ad hoc replacement rules should be necessary'
    for closure in closures:
        for dependency in closure['external_dependencies']:
            assert dependency['treatment'] == 'replace' and dependency['behavior_evidence']
            assert all(item['document'] == 'embedded:composer_conversion_knowledge'
                and item['content_hash'] for item in dependency['behavior_evidence'])
    assert {path: path.read_bytes() for path in root.rglob('*') if path.is_file()} == before
