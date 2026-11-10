"""Exercise the actual map-first runtime, wizard selection and pinned resume boundary."""

import json
from pathlib import Path
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace
from models.pipeline_configuration import PipelineConfiguration
from runtime.workspace_paths import run_database_path,run_report_path
from tools.state_store_tools.db import get_connection


@pytest.mark.parametrize('component_metadata', [False, True])
def test_full_indexed_start_automatically_prepares_then_stops_at_real_plan_approval(tmp_path, indexed_mapper_jar, monkeypatch, component_metadata):
    from tests.test_scoped_closure import workspace as xml_workspace
    from runtime.pipeline_runner import run_pipeline
    from runtime.java_toolchain import resolve_java_home
    root, vault = tmp_path / 'source', tmp_path / 'map'
    xml_workspace(root)
    if component_metadata:
        (root / '.project').write_text('<projectDescription><name>Bank</name></projectDescription>')
        (root / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/>'
            '<classpathentry kind="src" path="test"/>'
            '<classpathentry kind="con" path="org.eclipse.jst.j2ee.internal.module.container"/>'
            '<classpathentry kind="con" path="org.eclipse.jdt.junit.JUNIT_CONTAINER/4"/></classpath>')
        (root / 'test').mkdir()
        (root / 'test/LegacyTest.java').write_text('import org.junit.Test; public class LegacyTest {}')
        (root / '.settings').mkdir()
        (root / '.settings/org.eclipse.wst.common.component').write_text(
            '<project-modules><wb-module deploy-name="Bank"><wb-resource deploy-path="/" source-path="/src"/></wb-module></project-modules>')
    generate(indexed_mapper_jar, root, vault)
    if component_metadata:
        def forbidden_parse(*args, **kwargs):
            pytest.fail('Metadata supplement must not reparse Java or rescan source declarations')
        monkeypatch.setattr('tools.source_discovery_tools.discovery._index_classes', forbidden_parse)
        monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch', forbidden_parse)
    profile = PipelineConfiguration(source_root=str(root), existing_composer_map=str(vault), mapper_analysis_format='indexed-v1',
        mapper_vault_layout='scoped', source_workspace_id='bank', channels=['XML'], include_operations=['Flow'],
        output_root=str(tmp_path / 'runs'), java_version=25, java_home=resolve_java_home(25), model_provider='mock',
        scoped_native_mode='component_first_v1', conversion_strategy='behavior_units', plan_approval_policy='human',
        executable_verification=dict(mode='test_based_v1'), test_preparation=dict(mode='ai_shared_fixtures_v1'))
    monkeypatch.setattr('runtime.behavior_conversion.runner.generate', lambda *args, **kwargs: pytest.fail('AI called before human approval'))
    directory = run_pipeline(profile, 'automatic')
    with get_connection(str(run_database_path(directory))) as conn:
        row = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?', ('automatic',)).fetchone()
        assert tuple(row) == ('paused', 'conversion_plan_pending')
        assert conn.execute('SELECT count(*) FROM migration_plans WHERE run_id=?', ('automatic',)).fetchone()[0] == 1
    report = json.loads(run_report_path(directory, 'scoped_workflow_preparation.json').read_text())
    assert report['operations']['XML/Flow']['status'] == 'prepared'
    if component_metadata:
        supplement = json.loads((directory / 'state/eclipse-metadata.json').read_text())
        assert str(root / '.settings/org.eclipse.wst.common.component') in supplement['files']
        assert any(item['method'] == 'excluded_legacy_tests' for item in supplement['containers'])
        component = root / '.settings/org.eclipse.wst.common.component'
        component.write_text(component.read_text() + '\n')
        from runtime.checkpoints import resume_pipeline
        assert resume_pipeline(profile.output_root, 'automatic') == directory
        with get_connection(str(run_database_path(directory))) as conn:
            phase = conn.execute('SELECT current_phase FROM runs WHERE run_id=?', ('automatic',)).fetchone()[0]
            assert phase == 'conversion_scoped_stale'


@pytest.mark.parametrize('existing',[False,True])
def test_pipeline_uses_saved_facts_and_preserves_resume_gate(tmp_path,indexed_mapper_jar,monkeypatch,existing,caplog):
    from runtime import pipeline_runner
    from runtime.checkpoints import resume_pipeline
    from runtime.java_toolchain import resolve_java_home
    root=workspace(tmp_path/'source');vault=tmp_path/'map'
    if existing:generate(indexed_mapper_jar,root,vault)
    profile=PipelineConfiguration(source_root=str(root),mapper_jar=str(indexed_mapper_jar),
        existing_composer_map=str(vault) if existing else None,mapper_analysis_format='indexed-v1',
        mapper_vault_layout='scoped',source_workspace_id='bank',channels=['A'],include_operations=['Op'],
        output_root=str(tmp_path/'runs'),java_version=25,java_home=resolve_java_home(25),model_provider='mock')
    def forbidden(*args,**kwargs):pytest.fail('Map-first runtime entered whole-workspace discovery or syntax parsing')
    monkeypatch.setattr(pipeline_runner,'discover_java_sources',forbidden)
    monkeypatch.setattr('agents.legacy_composer_analysis.agent.import_vault',forbidden)
    monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch',forbidden)
    monkeypatch.setattr('tools.component_inventory_tools.xml_documents.read_xml',forbidden)
    import tools.composer_mapper_tools.indexed_analysis as reader
    original_digest=reader.digest;global_note_checks=[]
    def digest(path):
        if Path(path).suffix=='.md':global_note_checks.append(str(path))
        return original_digest(path)
    monkeypatch.setattr(reader,'digest',digest)
    caplog.set_level('INFO')
    directory=pipeline_runner.run_pipeline(profile,'indexed',tmp_path/'configs/bank.yaml')
    identity=json.loads((directory/'state/run_identity.json').read_text())
    assert identity['configuration_name']=='bank' and identity['run_id']=='indexed'
    if not existing:
        assert not any('/channels/B/operations/' in Path(path).as_posix() or 'Unrelated.md' in path for path in global_note_checks), 'Fresh map intake must check selected notes without globally rereading unused notes'
    assert (directory/'logs/intake.log').is_file()
    log=(directory/'logs/intake.log').read_text(encoding='utf-8')
    assert 'Validating reusable Composer map' in log
    assert 'zero workspace syntax scans' in log
    if not existing:assert (directory/'logs/mapper.log').stat().st_size>0
    report=json.loads(run_report_path(directory,'java_source_index.json').read_text())
    assert set(report['classes'])=={'pkg.Step','pkg.Helper','pkg.Leaf'}
    assert report['workspace_root']==str(root.resolve())
    assert report['class_projects']=={str(root/'src/pkg'/name):'.' for name in ('Step.java','Helper.java','Leaf.java')}
    assert run_report_path(directory,'java_classpath_index.json').is_file()
    conn=get_connection(str(run_database_path(directory)))
    try:
        assert conn.execute('SELECT current_phase FROM runs WHERE run_id=?',('indexed',)).fetchone()[0]=='scoped_inventory_ready'
        assert conn.execute('SELECT count(*) FROM source_implementations WHERE run_id=?',('indexed',)).fetchone()[0]==3
        assert [tuple(row) for row in conn.execute('SELECT channel,operation_id FROM scoped_operation_contexts')]==[('A','Op')]
        assert conn.execute('SELECT count(*) FROM map_analysis_snapshot').fetchone()[0]==1
        task=conn.execute("SELECT status,output_json FROM agent_tasks WHERE agent_name='LegacyComposerAnalysisAgent'").fetchone()
        assert task['status']=='completed'
        summary=json.loads(task['output_json'])['import_summary']
        assert summary['operations']==1 and summary['channel_operations']==1 and summary['java_classes']==3
        assert summary['errors']==[] and summary['unresolved_references']==[]
        assert conn.execute("SELECT count(*) FROM agent_tasks WHERE agent_name='LegacyComposerAnalysisAgent'").fetchone()[0]==1
    finally:conn.close()
    assert list((Path(profile.output_root)/'.map-validation').glob('*.json'))
    assert resume_pipeline(profile.output_root,'indexed')==directory
    assert json.loads((directory/'state/run_activity.json').read_text())['last_resumed_at']
    conn=get_connection(str(run_database_path(directory)))
    try:
        assert conn.execute('SELECT current_phase FROM runs WHERE run_id=?',('indexed',)).fetchone()[0]=='conversion_scoped_gated'
    finally:conn.close()
    from cli.discovery import discover_runs
    from models.common_models import RunConfig
    from tools.state_store_tools.runs import get_run, update_run_status
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    with get_connection(str(run_database_path(directory))) as conn:
        saved_config = RunConfig.model_validate(get_run(conn, 'indexed')['run_config_json'])
        definitions = conn.execute("SELECT count(*) FROM scoped_source_definitions WHERE run_id='indexed'").fetchone()[0]
    manifest = Path(saved_config.vault_root) / 'vault-manifest.json'
    before = file_digest(manifest)
    monkeypatch.setattr('tools.composer_mapper_tools.vault_importer.import_vault', forbidden)
    monkeypatch.setattr('tools.workspace_intake_tools.mapper_generation.mapper_command', forbidden)
    for phase in ('conversion_components_incomplete', 'conversion_components_failed',
                  'conversion_components_ready_for_composition', 'conversion_units_verifying'):
        with get_connection(str(run_database_path(directory))) as conn:
            update_run_status(conn, 'indexed', 'blocked', phase)
        assert 'indexed' in [run_id for run_id, _ in discover_runs(profile.output_root, resumable_only=True)]
        assert resume_pipeline(profile.output_root, 'indexed') == directory
        with get_connection(str(run_database_path(directory))) as conn:
            assert get_run(conn, 'indexed')['current_phase'] == 'conversion_scoped_gated'
            assert conn.execute("SELECT count(*) FROM scoped_source_definitions WHERE run_id='indexed'").fetchone()[0] == definitions
        assert file_digest(manifest) == before


def test_indexed_mapper_settings_and_reuse_command(tmp_path,indexed_mapper_jar):
    from tools.workspace_intake_tools.mapper_generation import mapper_command
    settings=dict(COMPOSER_ROOT=str(tmp_path/'source'),VAULT_ROOT=str(tmp_path/'map'),COMPOSER_MAPPER_JAR=str(indexed_mapper_jar),
        COMPOSER_MAPPER_VAULT_LAYOUT='scoped',SOURCE_WORKSPACE_ID='bank',COMPOSER_MAPPER_ANALYSIS_FORMAT='indexed-v1',
        COMPOSER_MAPPER_ANALYSIS_SETTINGS=dict(heap_mib=256,batch_files=25,batch_mib=2,java_file_mib=4,sqlite_cache_mib=8),
        COMPOSER_MAPPER_ANALYSIS_REUSE=str(tmp_path/'prior'))
    command=mapper_command(settings,markdown=True,filter_channel=False)
    assert command[:3]==['java','-Xmx256m','-jar']
    assert command[command.index('--analysis-batch-files')+1]=='25'
    assert command[-2:]==['--reuse-analysis',str(tmp_path/'prior')]
    assert '--channel' not in command
    with pytest.raises(ValueError):PipelineConfiguration(mapper_analysis=dict(batch_files=101))
    with pytest.raises(ValueError):PipelineConfiguration(mapper_analysis_format='indexed-v1')


def test_wizard_offers_indexed_analysis_without_work(tmp_path):
    from cli.composer_map_configuration import collect_composer_map_configuration
    choices=iter(['create','indexed-v1'])
    result=collect_composer_map_configuration(tmp_path,lambda *_:pytest.fail('No file generation or validation is needed'),
        lambda *_:next(choices))
    assert result==dict(mapper_analysis_format='indexed-v1',mapper_vault_layout='scoped')


def test_mapper_completions_advance_intake_but_repeated_heartbeat_does_not():
    from runtime.indexed_mapper_progress import IndexedMapperProgress
    from runtime.inventory_work import InventoryWork
    work=InventoryWork();observe=IndexedMapperProgress(work)
    observe('Progress: Indexing source 250/22000: source.java')
    assert work.completed==250 and work.total==22000
    last=work.last_work
    observe('Progress: Indexing source 250/22000: source.java | elapsed=00:10:00')
    assert work.last_work==last and work.completed==250
    observe('Progress: Indexing source 500/22000: next.java')
    assert work.completed==500
    observe('Rendered indexed note 100/24000')
    assert work.completed==100 and work.total==24000
