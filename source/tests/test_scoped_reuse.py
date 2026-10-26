"""Check qualified C5 cache reuse, consumer invalidation, and checkpoint boundaries."""

import json
from types import SimpleNamespace

import pytest

from test_scoped_closure import import_workspace
from test_scoped_vault_identity import scoped_mapper
from test_scoped_workflow import settings, prepare, pin
from models.java_classpath_index import JavaClasspathIndex
from tools.conversion_tools.scoped_reuse.checkpoint import ScopedCheckpointStale, validate_checkpoints
from tools.conversion_tools.scoped_reuse.state import checkpoints
from tools.state_store_tools.db import get_connection


@pytest.fixture(scope='module')
def seed(tmp_path_factory, scoped_mapper):
    folder = tmp_path_factory.mktemp('scoped-reuse')
    conn, root, vault = import_workspace(folder, scoped_mapper)
    config, profile = settings(root, vault)
    config.output_root = str(folder / 'generated')
    result = prepare(conn, config, profile)
    assert all(item['status'] == 'prepared' for item in result['operations'].values()), result
    yield conn, config, profile, result
    conn.close()


@pytest.fixture
def saved(seed):
    original, config, profile, result = seed
    conn = get_connection(':memory:')
    original.backup(conn)
    config = SimpleNamespace(**vars(config))
    profile = profile.model_copy(deep=True)
    from pathlib import Path
    roots = [Path(config.source_root), Path(config.vault_root)]
    files = {path: path.read_bytes() for root in roots for path in root.rglob('*') if path.is_file()}
    yield conn, config, profile, result
    for root in roots:
        for path in root.rglob('*'):
            if path.is_file() and path not in files and path.resolve().is_relative_to(root.resolve()):
                path.unlink()
    for path, content in files.items():
        path.write_bytes(content)
    conn.close()


def test_unchanged_workflow_reuses_proof_without_closure_analysis(saved, monkeypatch):
    conn, config, profile, first = saved
    from tools.conversion_tools.scoped_workflow import preparation
    monkeypatch.setattr(preparation, 'build_scoped_operation_closure', lambda *a, **k: pytest.fail('Unchanged closure rebuilt'))
    second = prepare(conn, config, profile)
    assert second['reused_contexts'] == sorted(first['operations'])
    assert second['operations'] == first['operations']
    assert not second['conversion_enabled']


def test_shared_implementations_reuse_once_but_units_stay_contextual(saved):
    conn, config, profile, report = saved
    entries = conn.execute("SELECT count(*) FROM scoped_reuse_entries WHERE category='implementation'").fetchone()[0]
    bindings = conn.execute("SELECT count(*) FROM scoped_reuse_consumers WHERE category='implementation'").fetchone()[0]
    assert bindings > entries > 0
    local, base = (report['operations'][key]['units'] for key in ('SME/Flow', 'XML/Flow'))
    assert not {unit['unit_id'] for unit in local} & {unit['unit_id'] for unit in base}
    from tools.conversion_tools.scoped_reuse.artifacts import load_bound_artifact
    records = checkpoints(conn, config.run_id)
    context = next(record for record in records.values() if record.operation_key == 'SME/Flow')
    alien = base[0]
    assert load_bound_artifact(conn, config.run_id, context, 'configured_unit', alien['unit_id'], alien['fingerprint']) is None


def test_source_change_invalidates_consumers_and_callers_and_is_sticky(saved):
    conn, config, profile, report = saved
    from pathlib import Path
    source = Path(config.source_root) / 'src/example/Work.java'
    previous = source.read_bytes()
    source.write_bytes(previous + b'\n// changed\n')
    with pytest.raises(ScopedCheckpointStale) as caught:
        prepare(conn, config, profile)
    assert set(caught.value.affected) == {'SME/Flow', 'XML/Flow', 'SME/Caller'}
    assert 'Changed selected called context' in caught.value.affected['SME/Caller']
    assert all(record.status == 'stale' for record in checkpoints(conn, config.run_id).values())
    assert conn.execute('SELECT count(*) FROM scoped_reuse_entries').fetchone()[0] > 0
    source.write_bytes(previous)
    with pytest.raises(ScopedCheckpointStale, match='Previously invalidated'):
        prepare(conn, config, profile)
    assert conn.execute('SELECT count(*) FROM source_artifacts').fetchone()[0] == 0


def test_local_xml_change_invalidates_only_its_qualified_consumers(saved):
    conn, config, profile, _ = saved
    from pathlib import Path
    source = Path(config.source_root) / 'Channel/SME/Caller.xml'
    source.write_text(source.read_text().replace('value="SME"', 'value="LOCAL_CHANGED"'))
    with pytest.raises(ScopedCheckpointStale) as caught:
        prepare(conn, config, profile)
    assert set(caught.value.affected) == {'SME/Caller', 'SME/Flow'}
    statuses = {record.operation_key: record.status for record in checkpoints(conn, config.run_id).values()}
    assert statuses['XML/Flow'] == 'current'
    assert prepare(conn, config, profile, selected={'XML/Flow'})['reused_contexts'] == ['XML/Flow']


@pytest.mark.parametrize('change', ['mapping', 'project', 'note', 'binding', 'profile', 'source_root', 'manifest', 'generation', 'schema', 'selection'])
def test_stale_input_categories_reject_reuse(saved, change):
    conn, config, profile, _ = saved
    from pathlib import Path
    root, vault = Path(config.source_root), Path(config.vault_root)
    if change == 'mapping':
        path = root / 'Channel/SME/dse.ini'
        path.write_text(path.read_text().replace('example.Field', 'example.ChangedField'))
    elif change == 'project':
        (root / '.classpath').write_text('<classpath/>')
    elif change == 'note':
        path = vault / 'channels/SME/channel.md'
        path.write_text(path.read_text() + '\nchanged')
    elif change == 'binding':
        identity = next(record.operation_identity for record in checkpoints(conn, config.run_id).values()
                        if record.operation_key == 'SME/Flow')
        conn.execute("UPDATE scoped_context_bindings SET definition_id='wrong-definition' WHERE operation_identity=? AND binding_kind='step' AND binding_key='0'", (identity,))
    elif change == 'profile':
        profile.java_version = 21
    elif change == 'source_root':
        config.source_root = str(root / 'missing-root')
    elif change == 'manifest':
        path = vault / 'vault-manifest.json'
        path.write_text(path.read_text() + '\n')
    elif change == 'schema':
        config.artifact_schema_version = 'changed-schema'
    elif change == 'selection':
        config.exclude_operations = ['Flow']
    else:
        (vault / 'vault-generation.json').write_text('{}')
    with pytest.raises(ScopedCheckpointStale):
        prepare(conn, config, profile)


def test_archive_bytes_are_part_of_freshness(tmp_path):
    from tools.conversion_tools.scoped_reuse.fingerprints import classpath_fingerprint
    path = tmp_path / 'dependency.jar'
    path.write_bytes(b'first archive')
    index = JavaClasspathIndex(classes={'org.example.Library': ['jar:' + str(path)]}, libraries=[str(path)])
    first = classpath_fingerprint(index)
    path.write_bytes(b'replacement archive')
    assert classpath_fingerprint(index) != first


def test_old_scoped_state_requires_explicit_replanning(saved):
    conn, config, profile, report = saved
    conn.execute('DELETE FROM scoped_checkpoints')
    old = dict(report, schema_version='scoped-v3-c4')
    conn.execute('UPDATE scoped_workflow_preparations SET preparation_json=?', (json.dumps(old),))
    with pytest.raises(ScopedCheckpointStale, match='predates'):
        prepare(conn, config, profile)


def test_output_reuse_requires_context_unit_files_and_validator(saved, tmp_path):
    conn, config, profile, report = saved
    from pathlib import Path
    from tools.conversion_tools.scoped_reuse.artifacts import save_validated_output, reuse_validated_output
    path = Path(config.output_root) / 'verified.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('validated output fixture')
    unit = report['operations']['SME/Flow']['units'][0]['unit_id']
    args = (conn, config, profile, JavaClasspathIndex(), 'SME/Flow', unit, 'native_artifact', 'RepeatedLabel')
    saved_id, fingerprint = save_validated_output(*args, {'result': 'fixture'}, [path], validator=lambda data: True)
    assert saved_id and fingerprint
    assert reuse_validated_output(*args, validator=lambda data: True) == {'result': 'fixture'}
    alien = (*args[:4], 'XML/Flow', *args[5:])
    assert reuse_validated_output(*alien, validator=lambda data: True) is None
    with pytest.raises(ValueError, match='validator rejected'):
        reuse_validated_output(*args, validator=lambda data: False)
    path.write_text('tampered')
    with pytest.raises(ValueError, match='bytes or metadata changed'):
        reuse_validated_output(*args, validator=lambda data: True)
    assert path.exists()


def test_output_paths_cannot_escape_the_run(saved, tmp_path):
    conn, config, profile, report = saved
    from tools.conversion_tools.scoped_reuse.artifacts import save_validated_output
    outside = tmp_path / 'outside.java'
    outside.write_text('outside')
    unit = report['operations']['SME/Flow']['units'][0]['unit_id']
    with pytest.raises(ValueError, match='within this run output root'):
        save_validated_output(conn, config, profile, JavaClasspathIndex(), 'SME/Flow', unit,
                              'native_artifact', 'unit', {}, [outside], validator=lambda data: True)


def test_generation_cannot_reuse_legacy_acceptance_for_scoped_run(saved):
    conn, config, profile, _ = saved
    from runtime.behavior_conversion.generation import generate
    from models.native_unit_bundle import NativeUnitBundle
    with pytest.raises(ValueError, match='conversion is gated'):
        generate(conn, config, profile, 'unit', 'Repeat', '', {}, NativeUnitBundle,
                 model_call=lambda *args: pytest.fail('Generation gate bypassed'))


def test_published_boundary_does_not_inherit_callee_source_invalidation(tmp_path, scoped_mapper):
    from pathlib import Path
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    pin(conn)
    prepare(conn, config, profile)
    source = Path(root) / 'src/example/Work.java'
    source.write_text(source.read_text() + '\n// callee-only change\n')
    report = prepare(conn, config, profile, selected={'SME/Caller'})
    assert report['reused_contexts'] == ['SME/Caller']
    records = {item.operation_key: item for item in checkpoints(conn, config.run_id).values()}
    assert records['SME/Caller'].status == 'current'
    assert records['SME/Flow'].status == 'stale'


def test_changed_registry_is_rejected_before_first_preparation(tmp_path, scoped_mapper):
    conn, root, vault = import_workspace(tmp_path, scoped_mapper)
    config, profile = settings(root, vault)
    path = root / 'Channel/SME/dse.ini'
    path.write_text(path.read_text() + '\n<!-- changed after intake -->')
    with pytest.raises(ScopedCheckpointStale, match='differs from intake'):
        prepare(conn, config, profile)
    assert not checkpoints(conn, config.run_id)


def test_proof_and_cache_metadata_tampering_are_rejected(saved):
    conn, config, profile, _ = saved
    record = next(item for item in checkpoints(conn, config.run_id).values() if item.operation_key == 'SME/Flow')
    conn.execute("UPDATE scoped_reuse_entries SET data_json='{}' WHERE category='workflow' AND identity=?", (record.operation_identity,))
    with pytest.raises(ValueError, match='metadata changed'):
        prepare(conn, config, profile, selected={'SME/Flow'})
    assert checkpoints(conn, config.run_id)[record.operation_identity].status == 'stale'


def test_changed_contract_rejects_the_caller_before_reuse(saved):
    conn, config, profile, _ = saved
    conn.execute("UPDATE operation_service_contracts SET fingerprint='changed' WHERE operation_key='SME/Flow'")
    with pytest.raises(ScopedCheckpointStale) as caught:
        prepare(conn, config, profile)
    assert {'SME/Caller', 'SME/Flow'} <= caught.value.affected.keys()


def test_output_validation_rechecks_source_after_validator(saved):
    from pathlib import Path
    from tools.conversion_tools.scoped_reuse.artifacts import save_validated_output
    conn, config, profile, report = saved
    unit = report['operations']['SME/Flow']['units'][0]['unit_id']
    def change_source(data):
        path = Path(config.source_root) / 'src/example/Work.java'
        path.write_text(path.read_text() + '\n// during validation')
        return True
    with pytest.raises(ScopedCheckpointStale):
        save_validated_output(conn, config, profile, JavaClasspathIndex(), 'SME/Flow', unit,
                              'result', 'same-label', {'result': 'fixture'}, [], validator=change_source)
    assert conn.execute("SELECT count(*) FROM scoped_reuse_entries WHERE category='result'").fetchone()[0] == 0


def test_runtime_reports_stale_contexts_without_rebuilding(saved, tmp_path, monkeypatch):
    from pathlib import Path
    from runtime.scoped_conversion import prepare_scoped_runtime
    from runtime.workspace_paths import run_report_path
    from tools.state_store_tools.runs import upsert_run, get_run
    from tools.conversion_tools.scoped_workflow import preparation
    conn, config, profile, _ = saved
    upsert_run(conn, run_id=config.run_id, run_mode='full_inventory')
    path = Path(config.source_root) / 'src/example/Work.java'
    path.write_text(path.read_text() + '\n// stale runtime')
    monkeypatch.setattr(preparation, 'discover_java_classpath', lambda *args: JavaClasspathIndex())
    monkeypatch.setattr(preparation, 'build_scoped_operation_closure', lambda *a, **k: pytest.fail('Stale closure rebuilt'))
    report = prepare_scoped_runtime(conn, config, profile, tmp_path)
    assert report['stale_contexts']
    assert get_run(conn, config.run_id)['current_phase'] == 'conversion_scoped_stale'
    assert not json.loads(run_report_path(tmp_path, 'scoped_workflow_preparation.json').read_text())['conversion_enabled']
