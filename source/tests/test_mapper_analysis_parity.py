"""Compare indexed products and source edges with stable mapper/converter behavior."""

from pathlib import Path
import json
import re
import subprocess

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,ROOT
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
from tools.component_inventory_tools import build_component_inventory
from tools.operation_call_tools.discovery import discover_operation_calls


def test_bank_demo_preserves_non_java_products_and_call_connections(tmp_path,indexed_mapper_jar):
    root=ROOT/'bank-demo/composer/Workspace';legacy=tmp_path/'legacy';indexed=tmp_path/'indexed'
    result=subprocess.run(['java','-jar',str(indexed_mapper_jar),'--root',str(root),'--vault',str(legacy),
        '--vault-layout','scoped','--workspace-id','bank','--md','true'],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stderr
    generate(indexed_mapper_jar,root,indexed)
    old=read_vault_manifest(legacy,allow_shared=True)
    with IndexedAnalysis(indexed) as new:
        expected={row['note']:{key:value for key,value in row.items() if key not in {'note_hash','qualified_consumers'}} for row in old['entities']}
        actual={row['note']:{key:value for key,value in row.items() if key!='note_hash'} for row in new['entities']}
        assert actual==expected
        for row in old['entities']:
            assert list(new.consumers(row['definition_id']))==row['qualified_consumers']
        assert list(new['operation_contexts'])==old['operation_contexts']
        for row in new['entities']:
            if row['kind']=='java_class':continue
            before=(legacy/row['note']).read_text(encoding='utf-8')
            after=(indexed/row['note']).read_text(encoding='utf-8')
            assert after.replace('vault_schema_version: 4','vault_schema_version: 3')==before,row['note']
    actual_graph,expected_graph=discover_operation_calls(indexed),discover_operation_calls(legacy)
    # The schema-four frontmatter intentionally gives each physical note a new digest.
    for graph in (actual_graph,expected_graph):
        graph['calls']=[{key:value for key,value in call.items() if key!='evidence_hash'} for call in graph['calls']]
    assert actual_graph==expected_graph


def test_project_visibility_and_reference_sites_match_converter(tmp_path,indexed_mapper_jar):
    root=tmp_path/'source'
    def project(name,refs=()):
        folder=root/name;folder.mkdir(parents=True)
        (folder/'.project').write_text('<projectDescription><name>'+name+'</name><projects>'+''.join('<project>'+ref+'</project>' for ref in refs)+'</projects></projectDescription>')
        (folder/'.classpath').write_text('<classpath><classpathentry kind="src" path="src"/></classpath>')
        return folder/'src'
    p=project('P',['C']);c=project('C');x=project('X')
    files={p/'p/Step.java':'package p; import static lib.Helper.value; import lib.*; class Step<T> { T generic; int run(){ return value()+Helper.value()+hidden.Secret.value(); } }',
           c/'lib/Helper.java':'package lib; public class Helper { public static int value(){ return Leaf.value(); } }',
           c/'lib/Leaf.java':'package lib; public class Leaf { public static int value(){ return 1; } }',
           x/'lib/Helper.java':'package lib; public class Helper { public static int value(){ return 9; } }',
           x/'hidden/Secret.java':'package hidden; public class Secret { public static int value(){ return 3; } }'}
    for path,text in files.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    for channel in ('XML','A'):
        folder=p/'Channel'/channel;folder.mkdir(parents=True);(folder/'dse.ini').write_text('<dse.ini/>')
    (p/'Channel/A/ops.xml').write_text('<XML><CCDSEServerOperation id="Op"><opStep id="S" implClass="p.Step"/></CCDSEServerOperation></XML>')
    baseline=build_component_inventory(root,'bank')
    paths={item.implementation_id:str(root/item.source_path) for item in baseline.implementations}
    expected={(paths[edge.caller_implementation_id],paths[edge.target_implementation_id],edge.source_offset,edge.reference_kind,edge.reference_name) for edge in baseline.java_dependencies.dependencies}
    generate(indexed_mapper_jar,root,tmp_path/'map')
    with IndexedAnalysis(tmp_path/'map') as analysis:
        assert set(analysis.conn.execute('SELECT caller,target,offset,kind,name FROM java_edges'))==expected
        issues={(paths[issue.implementation_id],issue.message) for issue in baseline.java_dependencies.issues}
        actual=set(analysis.conn.execute("SELECT json_extract(data,'$.file'),json_extract(data,'$.message') FROM records WHERE collection='dependency_issues'"))
        assert actual==issues
        from types import SimpleNamespace
        from tools.component_inventory_tools.mapped_inventory import MappedInventory
        from tools.composer_mapper_tools.mapped_scope import mapped_scope
        from tools.state_store_tools.inventory_records import InventoryRecords
        config=SimpleNamespace(target_channels=['A'],include_operations=['Op'],exclude_operations=[])
        mapped=MappedInventory(analysis,root,config)
        storage=InventoryRecords(tmp_path/'selected.sqlite',selection=config);storage.mapped_analysis=mapped
        try:
            with mapped_scope(mapped):
                selected=build_component_inventory(root,'bank',mapped.index,storage)
                assert {item.source_path for item in selected.implementations}=={'P/src/p/Step.java','C/src/lib/Helper.java','C/src/lib/Leaf.java'}
        finally:storage.close()
