"""Verify exact global counts, selected reads, bounded storage, and content-verified syntax reuse."""

import json
from pathlib import Path
from types import SimpleNamespace
import tracemalloc
from xml.etree import ElementTree

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.inventory_reports import write_json_report
from tools.component_inventory_tools import build_component_inventory
from tools.component_inventory_tools.conversion_scope import persist_conversion_scope
from tools.component_inventory_tools.library_planner import prepare_library_plan
from tools.source_discovery_tools import discover_java_sources
from tools.state_store_tools.component_inventory import persist_component_inventory, get_implementation_usage, get_conversion_inventory
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.inventory_records import InventoryRecords, RecordSequence
from tools.state_store_tools.workspace_analysis import WorkspaceAnalysis, content_hash


def workspace(root):
    sources = root / 'src/pkg'
    sources.mkdir(parents=True)
    for name, body in dict(Step='Helper.value() + Helper.value()', Helper='Leaf.value()', Leaf='1', Unrelated='2').items():
        (sources / (name + '.java')).write_text(f'package pkg; public class {name} {{ public static int value() {{ return {body}; }} }}')
    for channel in ('A', 'B', 'C'):
        folder = root / 'src/Channel' / channel
        folder.mkdir(parents=True)
        (folder / 'dse.ini').write_text('<dse.ini/>')
        (folder / 'ops.xml').write_text(f'<XML><CCDSEServerOperation id="Op"><opStep id="S" implClass="pkg.Step"/></CCDSEServerOperation></XML>')
    return root


def state():
    conn = get_connection(':memory:')
    create_all_tables(conn)
    return conn


def test_disk_inventory_matches_legacy_and_global_library_counts(tmp_path):
    root = workspace(tmp_path / 'workspace')
    index = discover_java_sources(str(root))
    legacy = build_component_inventory(root, 'bank', index)
    storage = InventoryRecords(tmp_path / 'records.sqlite')
    conn = state()
    try:
        stored = build_component_inventory(root, 'bank', index, storage)
        path = tmp_path / 'inventory.json'
        write_json_report(path, stored)
        actual = json.loads(path.read_text())
        expected = legacy.model_dump(mode='json')
        assert actual == expected
        persist_component_inventory(conn, 'old', legacy)
        persist_component_inventory(conn, 'new', stored)
        assert get_implementation_usage(conn, 'old') == get_implementation_usage(conn, 'new')
        migration = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel='A', operation_id='Op')])])
        profile = PipelineConfiguration(shared_library_min_usage=2)
        old = prepare_library_plan(conn, SimpleNamespace(run_id='old'), profile, migration)
        new = prepare_library_plan(conn, SimpleNamespace(run_id='new'), profile, migration)
        assert old.assignments == new.assignments
        assert old.usage_counts == new.usage_counts
        assert old.reference_counts == new.reference_counts
        assert all(count == 3 for count in new.usage_counts.values())
        implementations, uses, graph = get_conversion_inventory(conn, 'new', 'Op', 'A')
        assert {item['class_name'] for item in implementations.values()} == {'Step', 'Helper', 'Leaf'}
        scope = persist_conversion_scope(conn, SimpleNamespace(run_id='new', target_channels=['A'], include_operations=['Op'], exclude_operations=[]))
        assert scope['selected_operations'] == ['A/Op']
        assert scope['required_implementations'] == 3
    finally:
        storage.close()
        conn.close()


def test_batch_iterator_enforces_file_and_byte_limits(tmp_path, monkeypatch):
    from tools.java_analysis_tools.source_dependencies import parser
    paths = []
    for i in range(9):
        path = tmp_path / f'File{i}.java'
        path.write_text('x' * 20)
        paths.append(path)
    calls = []
    def parse(batch, **kwargs):
        calls.append(list(batch))
        for path in batch:
            yield ElementTree.Element('source', path=str(path))
    monkeypatch.setattr(parser, '_parse_batch', parse)
    assert len(list(parser.iter_source_references(paths, batch_files=3, batch_bytes=45))) == 9
    assert all(len(batch) <= 2 for batch in calls)


def test_syntax_cache_reuses_only_identical_complete_source_results(tmp_path, monkeypatch):
    from tools.java_analysis_tools.source_dependencies import parser
    root = workspace(tmp_path / 'workspace')
    paths = list((root / 'src/pkg').glob('*.java'))
    calls = []
    def parse(batch, **kwargs):
        calls.extend(batch)
        for path in batch:
            yield ElementTree.Element('source', path=str(path), package='pkg')
    monkeypatch.setattr(parser, '_parse_batch', parse)
    cache = WorkspaceAnalysis(tmp_path / 'cache.sqlite')
    cache.observe_workspace(root)
    try:
        list(parser.iter_source_references(paths, cache=cache))
        assert len(calls) == 4
        revision = cache.publish(root, discover_java_sources(str(root)))
        calls.clear()
        list(parser.iter_source_references(paths, cache=cache))
        assert calls == [] and cache.hits == 4
        paths[0].write_text('package pkg; class Changed {}')
        with pytest.raises(ValueError, match='changed'):
            list(parser.iter_source_references(paths, cache=cache))
        cache.observed.clear()
        cache.observe_workspace(root)
        list(parser.iter_source_references(paths, cache=cache))
        assert calls == [str(paths[0].resolve())]
        assert cache.publish(root, discover_java_sources(str(root))) != revision
        (root / 'src/.classpath').write_text('<classpath/>')
        with pytest.raises(ValueError, match='New source'):
            cache.publish(root, discover_java_sources(str(root)))
    finally:
        cache.close()


def test_streaming_report_and_records_scale_to_22000_entries(tmp_path):
    from models.java_source_dependencies import JavaDependencyUse
    storage = InventoryRecords(tmp_path / 'records.sqlite')
    mapping = storage.mapping('uses', JavaDependencyUse)
    tracemalloc.start()
    try:
        for index in range(22000):
            mapping[str(index)] = JavaDependencyUse(use_id=str(index), source_use_id='root', dependency_id='edge',
                operation_key=str(index), operation_id='Op', channel='A', implementation_id='shared', reference_count=2)
        report = tmp_path / 'uses.json'
        write_json_report(report, RecordSequence(mapping))
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 24 * 1024 * 1024
        assert len(mapping) == 22000
        assert report.stat().st_size > 1000000
    finally:
        tracemalloc.stop()
        storage.close()


def test_disk_cycle_counts_match_legacy_fallback(tmp_path):
    root = workspace(tmp_path / 'workspace')
    (root / 'src/pkg/Leaf.java').write_text('package pkg; public class Leaf { public static int value() { return Helper.value(); } }')
    index = discover_java_sources(str(root))
    legacy = build_component_inventory(root, 'bank', index)
    storage = InventoryRecords(tmp_path / 'cycle.sqlite')
    try:
        stored = build_component_inventory(root, 'bank', index, storage)
        assert {item.use_id: item.reference_count for item in stored.java_dependencies.uses} == {
            item.use_id: item.reference_count for item in legacy.java_dependencies.uses}
    finally:
        storage.close()


def test_production_intake_streams_reports_and_binds_completed_revision(tmp_path, monkeypatch):
    from runtime import pipeline_runner
    from runtime.java_toolchain import resolve_java_home
    root = workspace(tmp_path / 'workspace')
    vault = tmp_path / 'vault'
    (vault / 'analysis').mkdir(parents=True)
    (vault / 'analysis/channel-operation-registry.md').write_text('A\n')
    profile = PipelineConfiguration(source_root=str(root), existing_composer_map=str(vault),
        output_root=str(tmp_path / 'runs'), channels=['A'], include_operations=['Op'],
        model_provider='mock', java_home=resolve_java_home(25))
    monkeypatch.setattr(pipeline_runner, 'run_legacy_composer_analysis', lambda *args: {'paused': True})
    directory = pipeline_runner.run_pipeline(profile, 'selected')
    reports = directory / 'reports/1_intake_and_legacy_analysis'
    inventory = json.loads((reports / 'component_inventory.json').read_text())
    assert len(inventory['implementations']) == 3
    scope = json.loads((reports / 'conversion_scope.json').read_text())
    assert scope['required_implementations'] == 3
    assert scope['workspace_totals']['implementations'] == 4
    assert {use['channel'] for use in inventory['uses']} == {'A'}
    usage = json.loads((reports / 'component_usage.json').read_text())
    helper_usage = next(item for item in usage if item['implementation']['class_name'] == 'Helper')
    assert helper_usage['operation_count'] == 3
    assert {item['channel'] for item in helper_usage['consumers']} == {'A', 'B', 'C'}
    conn = get_connection(str(directory / 'state/migration.db'))
    try:
        assert conn.execute('SELECT revision FROM workspace_analysis_revision WHERE run_id=?', ('selected',)).fetchone()
        assert conn.execute('SELECT count(*) FROM java_dependency_edges').fetchone()[0] > 0
    finally:
        conn.close()


def test_snapshot_rejects_deletion_and_corrupt_syntax_cache_rebuilds(tmp_path):
    root = workspace(tmp_path / 'workspace')
    cache = WorkspaceAnalysis(tmp_path / 'cache.sqlite')
    path = root / 'src/pkg/Step.java'
    cache.observe_workspace(root)
    digest = content_hash(path)
    cache.store(path, digest, False, ElementTree.Element('source', path=str(path)))
    cache.conn.execute("UPDATE syntax SET xml='broken'")
    assert cache.read(path, digest, False) is None
    path.unlink()
    try:
        with pytest.raises(ValueError, match='removed'):
            cache.publish(root, discover_java_sources(str(root)))
        assert cache.conn.execute('SELECT count(*) FROM revisions').fetchone()[0] == 0
    finally:
        cache.close()


@pytest.mark.parametrize('aliases', [False, True])
def test_disk_xml_catalog_preserves_inherited_formats_and_selectors(tmp_path, aliases):
    from tests.test_component_inventory import make_workspace
    root, _ = make_workspace(tmp_path, aliases=aliases)
    index = discover_java_sources(str(root))
    legacy = build_component_inventory(root, 'bank', index)
    storage = InventoryRecords(tmp_path / 'xml.sqlite')
    try:
        stored = build_component_inventory(root, 'bank', index, storage)
        path = tmp_path / 'xml.json'
        write_json_report(path, stored)
        assert json.loads(path.read_text()) == legacy.model_dump(mode='json')
    finally:
        storage.close()


def test_cached_syntax_is_reresolved_when_a_class_is_added(tmp_path, monkeypatch):
    from tools.java_analysis_tools.source_dependencies import parser
    root = tmp_path / 'workspace'
    (root / 'src/pkg').mkdir(parents=True)
    step = root / 'src/pkg/Step.java'
    step.write_text('package pkg; class Step { Helper value; }')
    calls = []
    def parse(batch, **kwargs):
        for path in batch:
            calls.append(path)
            document = ElementTree.Element('source', path=path, package='pkg')
            if path.endswith('Step.java'):
                ElementTree.SubElement(document, 'reference', name='Helper', kind='type', offset='1')
            yield document
    monkeypatch.setattr(parser, '_parse_batch', parse)
    from tools.component_inventory_tools.stored_java_dependencies import build_stored_java_dependencies
    from tools.component_inventory_tools.identity import identify_java_source
    cache = WorkspaceAnalysis(tmp_path / 'cache.sqlite')
    try:
        for run in (1, 2):
            if run == 2:
                (root / 'src/pkg/Helper.java').write_text('package pkg; class Helper {}')
            cache.observed.clear()
            cache.observe_workspace(root)
            index = discover_java_sources(str(root))
            implementations = [identify_java_source(root, 'bank', root / 'src', path, name)
                               for name, paths in index.classes.items() for path in paths]
            storage = InventoryRecords(tmp_path / f'run{run}.sqlite', cache)
            try:
                graph = build_stored_java_dependencies(root, index, implementations, [], storage)
                assert len(graph.dependencies) == run - 1
            finally:
                storage.close()
        assert calls.count(str(step.resolve())) == 1
    finally:
        cache.close()


def test_operation_scope_includes_called_operations_without_overriding_exclusions(tmp_path):
    root = workspace(tmp_path / 'workspace')
    xml = root / 'src/Channel/A/ops.xml'
    xml.write_text('''<XML><CCDSEServerOperation id="Caller"><opStep id="Call"
        implClass="com.ibm.il.dse.cc.cut.CCComplexOpStep" opExecuteName="Op"/></CCDSEServerOperation>
        <CCDSEServerOperation id="Op"><opStep id="S" implClass="pkg.Step"/></CCDSEServerOperation></XML>''')
    inventory = build_component_inventory(root, 'bank')
    conn = state()
    try:
        persist_component_inventory(conn, 'scope', inventory)
        result = persist_conversion_scope(conn, SimpleNamespace(run_id='scope', target_channels=['A'],
            include_operations=['Caller'], exclude_operations=['Op']))
        assert result['selected_operations'] == ['A/Caller']
        assert result['required_operations'] == ['A/Caller', 'A/Op']
        assert result['excluded_required_operations'] == ['A/Op']
        assert result['required_implementations'] == 3
    finally:
        conn.close()


def test_22000_source_files_keep_global_sharing_and_selected_reads_bounded(tmp_path, monkeypatch):
    """Exercise real file discovery/storage with synthetic syntax, not dozens of JVM launches."""
    from tools.java_analysis_tools.source_dependencies import parser
    root = tmp_path / 'large'
    sources = root / 'src/scale'
    sources.mkdir(parents=True)
    for index in range(22000):
        (sources / f'C{index}.java').write_text(f'package scale; class C{index} {{ int value() {{ return Shared.value(); }} }}')
    (sources / 'Shared.java').write_text('package scale; class Shared { static int value() { return 1; } }')
    for channel in range(10):
        folder = root / f'src/Channel/CH{channel}'
        folder.mkdir(parents=True)
        (folder / 'dse.ini').write_text('<dse.ini/>')
        operations = ''.join(f'<CCDSEServerOperation id="Op{i}"><opStep id="S" implClass="scale.C{i}"/></CCDSEServerOperation>'
                             for i in range(channel, 220, 10))
        (folder / 'ops.xml').write_text('<XML>' + operations + '</XML>')
    batches = []
    def parse(batch, **kwargs):
        batches.append(len(batch))
        for path in batch:
            source = ElementTree.Element('source', path=str(path), package='scale')
            if not path.endswith('Shared.java'):
                ElementTree.SubElement(source, 'reference', name='Shared', kind='type', offset='1')
            yield source
    monkeypatch.setattr(parser, '_parse_batch', parse)
    storage = InventoryRecords(tmp_path / 'large.sqlite')
    conn = state()
    tracemalloc.start()
    try:
        index = discover_java_sources(str(root))
        inventory = build_component_inventory(root, 'large', index, storage)
        persist_component_inventory(conn, 'large', inventory)
        migration = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel='CH0', operation_id='Op0')])])
        plan = prepare_library_plan(conn, SimpleNamespace(run_id='large'), PipelineConfiguration(), migration)
        shared = next(item for item in inventory.implementations if item.class_name == 'Shared')
        assert plan.usage_counts['implementation:' + shared.implementation_id] == 220
        assert plan.assignments['implementation:' + shared.implementation_id] == 'common-lib'
        implementations, _, _ = get_conversion_inventory(conn, 'large', 'Op0', 'CH0')
        assert {item['class_name'] for item in implementations.values()} == {'C0', 'Shared'}
        write_json_report(tmp_path / 'large.json', inventory)
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 192 * 1024 * 1024
        assert sum(batches) == 22001 and max(batches) <= 250
    finally:
        tracemalloc.stop()
        storage.close()
        conn.close()
