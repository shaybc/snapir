"""Exercise the actual map-first runtime, wizard selection and pinned resume boundary."""

import json
from pathlib import Path
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace
from models.pipeline_configuration import PipelineConfiguration
from runtime.workspace_paths import run_database_path,run_report_path
from tools.state_store_tools.db import get_connection


def test_full_indexed_start_automatically_prepares_then_stops_at_real_plan_approval(tmp_path, indexed_mapper_jar, monkeypatch):
    from tests.test_scoped_closure import workspace as xml_workspace
    from runtime.pipeline_runner import run_pipeline
    from runtime.java_toolchain import resolve_java_home
    root, vault = tmp_path / 'source', tmp_path / 'map'
    xml_workspace(root)
    generate(indexed_mapper_jar, root, vault)
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
