"""Verify selected-only loading, exact global counts, immutable evidence and parse-free intake."""

from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.composer_mapper_tools.mapped_scope import mapped_scope
from tools.component_inventory_tools.mapped_inventory import MappedInventory
from tools.component_inventory_tools import build_component_inventory
from tools.state_store_tools.inventory_records import InventoryRecords
from tools.state_store_tools.db import create_all_tables,get_connection
from tools.state_store_tools.component_inventory import persist_component_inventory,get_implementation_usage


def selection():
    return SimpleNamespace(target_channels=['A'],include_operations=['Op'],exclude_operations=[])


def test_selected_intake_matches_full_global_counts_without_parsing(tmp_path,indexed_mapper_jar,monkeypatch):
    root=workspace(tmp_path/'source');vault=tmp_path/'map'
    generate(indexed_mapper_jar,root,vault)
    baseline=build_component_inventory(root,'bank')
    conn=get_connection(':memory:');create_all_tables(conn)
    persist_component_inventory(conn,'baseline',baseline)
    expected={row['implementation']['class_name']:row for row in get_implementation_usage(conn,'baseline')}
    def forbidden(*_args,**_kwargs):
        pytest.fail('Indexed intake must not parse source files')
    monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch',forbidden)
    monkeypatch.setattr('tools.component_inventory_tools.xml_documents.read_xml',forbidden)
    with IndexedAnalysis(vault) as analysis:
        analysis.verify_sources(root)
        mapped=MappedInventory(analysis,root,selection())
        with mapped_scope(mapped):
            storage=InventoryRecords(tmp_path/'records.sqlite',selection=selection());storage.mapped_analysis=mapped
            try:
                inventory=build_component_inventory(root,'bank',mapped.index,storage)
                assert {item.class_name for item in inventory.implementations}=={'Step','Helper','Leaf'}
                assert {use.channel for use in inventory.uses}=={'A'}
                persist_component_inventory(conn,'mapped',inventory,analysis['analysis_hash'])
                actual={row['implementation']['class_name']:row for row in get_implementation_usage(conn,'mapped')}
                assert actual=={name:expected[name] for name in actual}
                assert actual['Leaf']['operation_count']==3
                from tools.component_inventory_tools.library_planner import prepare_library_plan
                from models.pipeline_configuration import PipelineConfiguration
                migration=SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel='A',operation_id='Op')])])
                profile=PipelineConfiguration(source_root=str(root),source_workspace_id='bank',mapper_vault_layout='scoped',channels=['A'])
                before=prepare_library_plan(conn,SimpleNamespace(run_id='baseline'),profile,migration)
                after=prepare_library_plan(conn,SimpleNamespace(run_id='mapped'),profile,migration)
                assert after.usage_counts==before.usage_counts
                assert after.reference_counts==before.reference_counts
                assert after.assignments==before.assignments
            finally:
                storage.close()
    conn.close()


@pytest.mark.parametrize('change',['modify','add','remove'])
def test_stale_map_fails_before_intake(tmp_path,indexed_mapper_jar,change):
    root=workspace(tmp_path/'source');vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    path=root/'src/pkg/Unrelated.java'
    if change=='modify':path.write_text(path.read_text()+'\n// changed')
    elif change=='remove':path.unlink()
    else:(root/'src/pkg/Added.java').write_text('package pkg; class Added {}')
    with IndexedAnalysis(vault) as analysis,pytest.raises(ValueError,match='stale|changed'):
        analysis.verify_sources(root)


def test_unchanged_and_single_file_fact_reuse(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source');first=tmp_path/'first';generate(indexed_mapper_jar,root,first)
    second=tmp_path/'second';_,log=generate(indexed_mapper_jar,root,second,'--reuse-analysis',first)
    assert 'Parsed ' not in log.read_text(encoding='utf-8')
    assert json.loads((second/'vault-manifest.json').read_text())['reused_note_count']>0
    for path in first.rglob('*.md'):
        assert path.read_bytes()==(second/path.relative_to(first)).read_bytes()
    changed=root/'src/pkg/Leaf.java';changed.write_text(changed.read_text().replace('return 1','return 3'))
    _,log=generate(indexed_mapper_jar,root,tmp_path/'third','--reuse-analysis',second)
    text=log.read_text(encoding='utf-8')
    assert text.count('Parsed ')==1 and 'Parsed 1/1 Java files' in text


def test_reuse_rejects_modified_previous_note_without_overwriting_original(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source');first=tmp_path/'first';generate(indexed_mapper_jar,root,first)
    note=next(first.rglob('operation.md'));note.write_text('modified outside mapper')
    result,log=generate(indexed_mapper_jar,root,tmp_path/'second','--reuse-analysis',first,check=False)
    assert result.returncode
    assert 'note changed' in log.read_text(encoding='utf-8')
    assert note.read_text()=='modified outside mapper'
    assert not (tmp_path/'second/vault-manifest.json').exists()


def test_failed_analysis_recovers_only_complete_file_facts(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source');bad=root/'src/pkg/Broken.java';bad.write_text('package pkg; class Broken { invalid! }')
    failed=tmp_path/'failed';result,_=generate(indexed_mapper_jar,root,failed,check=False)
    assert result.returncode and (failed/'vault-generation.json').exists()
    assert not (failed/'vault-manifest.json').exists()
    bad.write_text('package pkg; class Broken {}')
    _,log=generate(indexed_mapper_jar,root,tmp_path/'recovered','--resume-analysis',failed)
    assert 'Parsed 1/1 Java files' in log.read_text(encoding='utf-8')


def test_descriptor_is_small_and_database_is_self_contained(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source');vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    descriptor=json.loads((vault/'vault-manifest.json').read_text())
    assert 'entities' not in descriptor and 'operation_contexts' not in descriptor
    assert (vault/'vault-manifest.json').stat().st_size<65536
    assert not (vault/'analysis/analysis.sqlite-wal').exists()
    with IndexedAnalysis(vault) as analysis:
        assert len(analysis['entities'])>0
    database=vault/'analysis/analysis.sqlite'
    with database.open('ab') as output:output.write(b'corrupt')
    with pytest.raises(ValueError,match='changed|truncated'):
        IndexedAnalysis(vault)


def test_xml_facts_preserve_utf16_namespaces_cdata_and_occurrence_tails(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    xml='''<?xml version="1.0" encoding="UTF-16"?>
<XML xmlns="urn:bank">
  <CCDSEServerOperation id="Op">
    <opStep id="S" implClass="pkg.Step"><field id="value"><![CDATA[hello & goodbye]]></field></opStep>
  </CCDSEServerOperation>
</XML>'''
    (root/'src/Channel/A/ops.xml').write_bytes(xml.encode('utf-16'))
    expected=build_component_inventory(root,'bank')
    by_id={definition.definition_id:definition for definition in expected.definitions}
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    with IndexedAnalysis(vault) as analysis:
        mapped=MappedInventory(analysis,root,selection())
        storage=InventoryRecords(tmp_path/'inventory.sqlite',selection=selection());storage.mapped_analysis=mapped
        try:
            with mapped_scope(mapped):
                actual=build_component_inventory(root,'bank',mapped.index,storage)
                for definition in actual.definitions:
                    assert definition==by_id[definition.definition_id]
        finally:
            storage.close()


def test_validation_receipt_skips_full_note_reads_but_checks_database(tmp_path,indexed_mapper_jar,monkeypatch):
    root=workspace(tmp_path/'source');vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    receipt=tmp_path/'validation.json'
    with IndexedAnalysis(vault,receipt=receipt):pass
    import tools.composer_mapper_tools.indexed_analysis as module
    module._validated.clear();original=module.digest
    def digest(path):
        assert Path(path).suffix!='.md','A validated immutable generation must not reread every note'
        return original(path)
    monkeypatch.setattr(module,'digest',digest)
    with IndexedAnalysis(vault,receipt=receipt):pass


def test_publisher_receipt_still_rejects_tampered_selected_note(tmp_path,indexed_mapper_jar):
    from tools.composer_mapper_tools.indexed_vault_importer import import_indexed_vault
    from tools.composer_mapper_tools.vault_importer import VaultImportSummary
    from tools.workspace_intake_tools.run_factory import create_run_config
    import constants
    root=workspace(tmp_path/'source');vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    conn=get_connection(':memory:');create_all_tables(conn)
    settings={key:getattr(constants,key) for key in dir(constants) if key.isupper()}
    settings.update(COMPOSER_ROOT=str(root),VAULT_ROOT=str(vault),TARGET_CHANNELS=['A'],
        INCLUDE_OPERATIONS=['Op'],EXCLUDE_OPERATIONS=[],RUN_MODE='single_channel')
    config=create_run_config(settings,'tampered')
    try:
        with IndexedAnalysis(vault,trusted_publication=True,receipt=tmp_path/'receipt.json') as analysis:
            mapped=MappedInventory(analysis,root,config)
            note=analysis.conn.execute("SELECT note FROM operation_context_index WHERE channel='A' AND name='Op'").fetchone()[0]
            (vault/note).write_text('modified selected operation')
            with pytest.raises(ValueError,match='Selected indexed note changed'):
                import_indexed_vault(conn,analysis,mapped,config,VaultImportSummary())
            assert conn.execute("SELECT name FROM sqlite_master WHERE name='scoped_vault_runs'").fetchone() is None
    finally:conn.close()
