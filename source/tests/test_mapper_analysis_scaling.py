"""Run real constrained-heap analysis with 22,000 Java files; no mocked scan counts."""

import os
from pathlib import Path
from types import SimpleNamespace
from time import monotonic
import json
import tracemalloc
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.component_inventory_tools.mapped_inventory import MappedInventory
from tools.composer_mapper_tools.mapped_scope import mapped_scope
from tools.state_store_tools.inventory_records import InventoryRecords
from tools.component_inventory_tools import build_component_inventory
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.component_inventory import persist_component_inventory,get_implementation_usage


@pytest.mark.skipif(os.environ.get('SNAPIR_REAL_SCALE_TEST')!='1',reason='Opt-in real 22,000-file constrained-heap acceptance run')
def test_real_22000_java_files_keep_selected_detail_small(tmp_path,indexed_mapper_jar,monkeypatch):
    root=Path(os.environ['SNAPIR_SCALE_SOURCE']) if os.environ.get('SNAPIR_SCALE_SOURCE') else tmp_path/'source'
    sources=root/'src/pkg';sources.mkdir(parents=True,exist_ok=True)
    for number in range(0 if os.environ.get('SNAPIR_SCALE_SOURCE') else 21998):
        name=f'Step{number:05d}'
        (sources/(name+'.java')).write_text(f'package pkg; public class {name} {{ public static int value() {{ return Helper.value()+Helper.value(); }} }}')
    (sources/'Helper.java').write_text('package pkg; public class Helper { public static int value() { return Leaf.value(); } }')
    (sources/'Leaf.java').write_text('package pkg; public class Leaf { public static int value() { return 1; } }')
    for channel in ('XML','A'):
        folder=root/'src/Channel'/channel;folder.mkdir(parents=True,exist_ok=True)
        (folder/'dse.ini').write_text('<dse.ini/>')
    folder=root/'src/Channel/A'
    for number in range(1000):
        (folder/f'operation{number:05d}.xml').write_text(f'<XML><CCDSEServerOperation id="Op{number:05d}"><opStep id="S" implClass="pkg.Step{number:05d}"/></CCDSEServerOperation></XML>')
    started=monotonic();vault=Path(os.environ['SNAPIR_SCALE_MAP']) if os.environ.get('SNAPIR_SCALE_MAP') else tmp_path/'map'
    if not os.environ.get('SNAPIR_SCALE_MAP'):generate(indexed_mapper_jar,root,vault,heap='256m',timeout=1800)
    reused=bool(os.environ.get('SNAPIR_SCALE_MAP'))
    mapping=None if reused else monotonic()-started
    config=SimpleNamespace(target_channels=['A'],include_operations=['Op00000'],exclude_operations=[])
    def forbidden(*_args,**_kwargs):pytest.fail('Scale intake cannot launch the Java scanner')
    monkeypatch.setattr('tools.java_analysis_tools.source_dependencies.parser._parse_batch',forbidden)
    with IndexedAnalysis(vault,trusted_publication=not reused,progress=lambda message:print(message,flush=True)) as analysis:
        assert analysis.conn.execute('SELECT count(*) FROM java_sources').fetchone()[0]==22000
        tracemalloc.start();started=monotonic()
        mapped=MappedInventory(analysis,root,config)
        print('Selected metadata ready after',monotonic()-started,'seconds',flush=True)
        with mapped_scope(mapped):
            storage=InventoryRecords(tmp_path/'inventory.sqlite',selection=config);storage.mapped_analysis=mapped
            class Progress:
                def stage(self,name,total=None):print('Scale intake phase:',name,'total=',total,'elapsed=',monotonic()-started,flush=True)
                def advance(self,**kwargs):pass
                def current(self,*args):pass
            storage.progress=Progress()
            conn=get_connection(':memory:');create_all_tables(conn)
            try:
                inventory=build_component_inventory(root,'bank',mapped.index,storage)
                assert len(inventory.implementations)==3
                assert len(inventory.uses)==1
                persist_component_inventory(conn,'scale',inventory,analysis['analysis_hash'])
                usage={row['implementation']['class_name']:row for row in get_implementation_usage(conn,'scale')}
                assert usage['Leaf']['operation_count']==1000
                assert usage['Leaf']['indirect_reference_count']==2000
                _,peak=tracemalloc.get_traced_memory()
                assert peak<64*1024*1024
                result=dict(java_files=22000,operations=1000,mapper_heap='256m',map_reused=reused,mapping_seconds=mapping,
                    selected_intake_seconds=monotonic()-started,selected_java_files=3,python_traced_peak_bytes=peak,
                    database_bytes=analysis.database.stat().st_size)
                (tmp_path/'measurements.json').write_text(json.dumps(result,indent=2))
                print(json.dumps(result),flush=True)
            finally:
                tracemalloc.stop();storage.close();conn.close()
