"""Protect channel overrides, large XML cursors and controlled resource-limit failures."""

from pathlib import Path
from types import SimpleNamespace
import pytest
from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.composer_mapper_tools.mapped_scope import mapped_scope
from tools.component_inventory_tools.mapped_inventory import MappedInventory
from tools.component_inventory_tools import build_component_inventory
from tools.state_store_tools.inventory_records import InventoryRecords


def test_imported_operation_uses_consuming_channel_java_override(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    (root/'src/Channel/A/dse.ini').write_text('''<dse.ini><kColl id="settings"><kColl id="tags"><kColl id="opSteps">
        <field id="Work" value="pkg.Step"/></kColl></kColl></kColl></dse.ini>''')
    (root/'src/Channel/A/ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><opStep id="Work"/></CCDSEServerOperation></XML>')
    (root/'src/Channel/B/dse.ini').write_text('''<dse.ini><kColl id="import"><field id="A"/></kColl>
        <kColl id="settings"><kColl id="tags"><kColl id="opSteps"><field id="Work" value="pkg.Unrelated"/>
        </kColl></kColl></kColl></dse.ini>''')
    # A local caller makes the inherited operation's consuming B view explicit.
    (root/'src/Channel/B/ops.xml').write_text('<XML><CCDSEServerOperation id="Caller"><opStep id="Call" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Op"/></CCDSEServerOperation></XML>')
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    config=SimpleNamespace(target_channels=['B'],include_operations=['Op'],exclude_operations=[])
    with IndexedAnalysis(vault) as analysis:
        mapped=MappedInventory(analysis,root,config)
        storage=InventoryRecords(tmp_path/'records.sqlite',selection=config);storage.mapped_analysis=mapped
        try:
            with mapped_scope(mapped):
                inventory=build_component_inventory(root,'bank',mapped.index,storage)
                assert {item.class_name for item in inventory.implementations}=={'Unrelated'}
                assert len(inventory.uses)==1
                assert not [item for item in inventory.uses if item.resolution_issue]
            roots=list(analysis.conn.execute('SELECT implementation FROM operation_roots r JOIN canonical_definitions d ON d.node=r.operation WHERE d.channel=\'A\''))
            assert roots==[(str(root/'src/pkg/Step.java'),)]
        finally:storage.close()


def test_one_xml_file_with_many_operations_and_thousand_steps(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    text='<!DOCTYPE XML SYSTEM "https://example.invalid/never-download.dtd"><XML>'
    text+=''.join(f'<CCDSEServerOperation id="Many{i}"><opStep id="S" implClass="pkg.Step"/></CCDSEServerOperation>' for i in range(300))
    text+='<CCDSEServerOperation id="Op">'+''.join(f'<opStep id="Repeated" implClass="pkg.Step" value="{i}"/>' for i in range(1000))+'</CCDSEServerOperation></XML>'
    (root/'src/Channel/A/ops.xml').write_text(text)
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault,heap='256m')
    with IndexedAnalysis(vault) as analysis:
        context=next(analysis._context(row) for row in analysis.conn.execute("SELECT identity,data FROM operation_context_index WHERE channel='A' AND name='Op'"))
        assert len(context['step_notes'])==1000
        assert len(set(context['step_notes']))==1000
        assert analysis.conn.execute('SELECT count(*) FROM operation_context_index WHERE channel=\'A\'').fetchone()[0]==301


def test_oversized_xml_definition_fails_without_publishing_ready_map(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    (root/'src/Channel/A/ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><opStep id="S" implClass="pkg.Step" value="'+'x'*(2*1024*1024)+'"/></CCDSEServerOperation></XML>')
    vault=tmp_path/'map';result,log=generate(indexed_mapper_jar,root,vault,heap='256m',check=False)
    assert result.returncode
    assert 'materialization budget' in log.read_text(encoding='utf-8')
    assert not (vault/'vault-manifest.json').exists()
    assert (vault/'vault-generation.json').exists()


def test_only_for_keeps_inactive_java_out_of_selected_closure(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    (root/'src/Channel/A/ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><opStep id="Active" implClass="pkg.Unrelated" onlyFor="A"/><opStep id="Other" implClass="pkg.Step" onlyFor="B"/></CCDSEServerOperation></XML>')
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    config=SimpleNamespace(target_channels=['A'],include_operations=['Op'],exclude_operations=[])
    with IndexedAnalysis(vault) as analysis:
        mapped=MappedInventory(analysis,root,config)
        storage=InventoryRecords(tmp_path/'records.sqlite',selection=config);storage.mapped_analysis=mapped
        try:
            with mapped_scope(mapped):
                inventory=build_component_inventory(root,'bank',mapped.index,storage)
                assert {item.class_name for item in inventory.implementations}=={'Unrelated'}
                assert len(inventory.uses)==1
                assert not [item for item in inventory.uses if item.resolution_issue]
            assert analysis.conn.execute("SELECT count(*) FROM operation_roots r JOIN canonical_definitions d ON d.node=r.operation WHERE d.channel='A'").fetchone()[0]==2
        finally:storage.close()


def test_inherited_format_override_selects_actual_context_reference(tmp_path,indexed_mapper_jar):
    root=workspace(tmp_path/'source')
    (root/'src/Channel/A/ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><refFormat name="csRequestFormat" refid="Fmt"/></CCDSEServerOperation><fmtDef id="Fmt"><Value implClass="pkg.Step"/></fmtDef></XML>')
    (root/'src/Channel/B/dse.ini').write_text('<dse.ini><kColl id="import"><field id="A"/></kColl></dse.ini>')
    (root/'src/Channel/B/ops.xml').write_text('<XML><CCDSEServerOperation id="Caller"><opStep id="Call" implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Op"/></CCDSEServerOperation><fmtDef id="Fmt"><Value implClass="pkg.Unrelated"/></fmtDef></XML>')
    vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    config=SimpleNamespace(target_channels=['B'],include_operations=['Op'],exclude_operations=[])
    with IndexedAnalysis(vault) as analysis:
        mapped=MappedInventory(analysis,root,config)
        storage=InventoryRecords(tmp_path/'records.sqlite',selection=config);storage.mapped_analysis=mapped
        try:
            with mapped_scope(mapped):
                inventory=build_component_inventory(root,'bank',mapped.index,storage)
                assert {item.class_name for item in inventory.implementations}=={'Unrelated'}
                assert {use.definition_path for use in inventory.uses if use.component_kind=='format'}=={'src/Channel/B/ops.xml'}
        finally:storage.close()
