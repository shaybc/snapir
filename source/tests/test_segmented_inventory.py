"""Compare segmented evidence/global factors with the original full expansion and test fan-out."""

import hashlib
import json
from types import SimpleNamespace
from time import monotonic

import pytest

from models.component_usage import ConfiguredComponentDefinition, ConfiguredComponentUse
from models.source_component_identity import SourceImplementationRecord
from models.stored_component_inventory import StoredComponentInventory, StoredJavaDependencyGraph
from models.java_source_dependencies import JavaDependencyUse, JavaSourceDependency
from models.pipeline_configuration import PipelineConfiguration
from tools.component_inventory_tools import build_component_inventory
from tools.component_inventory_tools.library_planner import prepare_library_plan
from tools.component_inventory_tools.segmented_java_usage import build_segmented_usage
from tools.source_discovery_tools import discover_java_sources
from tools.state_store_tools.component_inventory import persist_component_inventory, get_implementation_usage
from tools.state_store_tools.inventory_records import InventoryRecords, RecordSequence, DefinitionCatalog
from tools.state_store_tools.java_usage import iter_global_java_usage
from tests.test_inventory_scaling import workspace, state
from pathlib import Path


@pytest.mark.parametrize('cycle', [False, True])
@pytest.mark.parametrize('disk_traversal', [False, True, 'weighted_links'])
def test_segmented_counts_match_full_expansion_and_library_placement(tmp_path, monkeypatch, cycle, disk_traversal):
    if disk_traversal == 'weighted_links':
        monkeypatch.setattr('tools.component_inventory_tools.segmented_java_usage.COMPACT_GRAPH_EDGE_LIMIT', 3 if cycle else 2)
        def unexpected_disk_traversal(*args):
            pytest.fail('Repeated reference sites must share one compact class-to-class link')
        monkeypatch.setattr('tools.component_inventory_tools.segmented_java_usage.prepare_root_counts', unexpected_disk_traversal)
    elif disk_traversal:
        monkeypatch.setattr('tools.component_inventory_tools.segmented_java_usage.COMPACT_GRAPH_EDGE_LIMIT', 0)
    root = workspace(tmp_path / 'workspace')
    if cycle:
        (root / 'src/pkg/Leaf.java').write_text('package pkg; public class Leaf { public static int value() { return Helper.value(); } }')
    index = discover_java_sources(str(root))
    legacy = build_component_inventory(root, 'bank', index)
    selection = SimpleNamespace(target_channels=['A'], include_operations=['Op'], exclude_operations=[])
    storage = InventoryRecords(tmp_path / 'segmented.sqlite', selection=selection)
    conn = state()
    try:
        segmented = build_component_inventory(root, 'bank', index, storage)
        assert {use.channel for use in segmented.java_dependencies.uses} == {'A'}
        assert len(segmented.java_dependencies.uses) * 3 == len(legacy.java_dependencies.uses)
        persist_component_inventory(conn, 'old', legacy)
        persist_component_inventory(conn, 'new', segmented)
        new = get_implementation_usage(conn, 'new')
        targets = {item['implementation']['implementation_id'] for item in new}
        old = [item for item in get_implementation_usage(conn, 'old') if item['implementation']['implementation_id'] in targets]
        assert old == new
        migration = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel='A', operation_id='Op')])])
        profile = PipelineConfiguration(shared_library_min_usage=2)
        old_plan = prepare_library_plan(conn, SimpleNamespace(run_id='old'), profile, migration)
        new_plan = prepare_library_plan(conn, SimpleNamespace(run_id='new'), profile, migration)
        assert old_plan.assignments == new_plan.assignments
        assert old_plan.usage_counts == new_plan.usage_counts
        assert old_plan.reference_counts == new_plan.reference_counts
        from tools.state_store_tools.component_inventory import get_conversion_inventory
        with pytest.raises(ValueError, match='outside this run'):
            get_conversion_inventory(conn, 'new', 'Op', 'B')
    finally:
        storage.close()
        conn.close()


@pytest.mark.parametrize('repeated_step', [False, True])
def test_shared_fanout_does_not_expand_unselected_operation_times_reference_sites(tmp_path, repeated_step):
    selection = SimpleNamespace(target_channels=['A'], include_operations=['Op0'], exclude_operations=[])
    storage = InventoryRecords(tmp_path / 'fanout.sqlite', selection=selection)
    conn = storage.conn
    DefinitionCatalog(storage)
    uses = storage.mapping('uses', ConfiguredComponentUse)
    details = storage.mapping('dependency_uses', JavaDependencyUse)
    xml = '<opStep id="S" implClass="pkg.Root"/>'
    digest = hashlib.sha256(xml.encode()).hexdigest()
    operation_count, edge_count = 5000, 100
    for i in range(operation_count):
        selected = i == 0 or repeated_step and i == 1
        key = '0' if selected else str(i)
        uses[str(i)] = ConfiguredComponentUse(use_id=str(i), definition_id='step', operation_key=key,
            operation_id='Op0' if selected else f'Op{i}', channel='A' if selected else 'OTHER', component_kind='opStep',
            definition_path='ops.xml', definition_selector='/step', configuration_hash=digest,
            configuration_xml=xml, implementation_id='Root', referenced_by='operation')
    conn.execute('CREATE TABLE graph_edges (identity TEXT PRIMARY KEY,caller TEXT,target TEXT)')
    conn.execute('CREATE INDEX graph_callers ON graph_edges(caller)')
    conn.execute('CREATE INDEX graph_targets ON graph_edges(target)')
    for i in range(edge_count):
        conn.execute('INSERT INTO graph_edges VALUES (?,?,?)', (str(i), 'Root' if i == 0 else f'H{i-1}', f'H{i}'))
    started = monotonic()
    try:
        factors = build_segmented_usage(storage, [SimpleNamespace(implementation_id='Root', class_name='Root')], details)
        assert len(details) == edge_count * (2 if repeated_step else 1)
        assert conn.execute('SELECT count(*) FROM usage_roots').fetchone()[0] == operation_count - int(repeated_step)
        assert conn.execute('SELECT count(*) FROM usage_counts').fetchone()[0] == edge_count
        # The original global expansion would have produced 500,000 full use records.
        assert edge_count * operation_count == 500000
        print(f'5000-operation/100-edge fan-out built in {monotonic()-started:.3f}s; detail rows={len(details)}')
        records = [SourceImplementationRecord(implementation_id=name, workspace_id='fanout', source_root='src',
            source_path=f'{name}.java', package_name='pkg', class_name=name, source_hash='hash')
            for name in ['Root', *(f'H{i}' for i in range(edge_count))]]
        graph = StoredJavaDependencyGraph(uses=RecordSequence(details))
        graph.usage_factors = factors
        inventory = StoredComponentInventory(workspace_id='fanout', implementations=records,
            uses=RecordSequence(uses), java_dependencies=graph)
        main = state()
        try:
            persist_component_inventory(main, 'fanout', inventory)
            summary = list(iter_global_java_usage(main, 'fanout', implementation_id='H99'))
            assert sum(item.reference_count for item in summary) == operation_count
            assert len({item.operation_key for item in summary}) == operation_count - int(repeated_step)
        finally:
            main.close()
    finally:
        storage.close()


def test_repeated_class_ownership_does_not_resolve_every_project_for_every_use(tmp_path, monkeypatch):
    from models.java_source_index import JavaSourceIndex
    root = tmp_path / 'workspace'
    source = root / 'src/pkg/Root.java'
    source.parent.mkdir(parents=True)
    source.write_text('package pkg; public class Root {}')
    folder = root / 'src/Channel/A'
    folder.mkdir(parents=True)
    (folder / 'ops.xml').write_text('<XML>' + ''.join(
        f'<CCDSEServerOperation id="Op{i}"><opStep id="S" implClass="pkg.Root"/></CCDSEServerOperation>' for i in range(200)) + '</XML>')
    roots = {'own': [str((root / 'src').resolve())]}
    for i in range(50):
        path = root / f'project{i}/src'
        path.mkdir(parents=True)
        roots[str(i)] = [str(path.resolve())]
    location = str(source.resolve())
    index = JavaSourceIndex(workspace_root=str(root.resolve()), source_roots=roots,
        classes={'pkg.Root': [location]}, class_projects={location: 'own'})
    monkeypatch.setattr('tools.component_inventory_tools.java_dependencies.iter_source_references', lambda *args, **kwargs: iter(()))
    original = Path.resolve
    calls = []
    def resolve(path, *args, **kwargs):
        calls.append(str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    inventory = build_component_inventory(root, 'bank', index)
    assert len(inventory.uses) == 200
    assert len(calls) < 200
