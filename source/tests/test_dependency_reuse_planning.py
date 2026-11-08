"""Check artifact integrity, recovery and API pin transactions during dependency planning."""
from copy import deepcopy
import hashlib

from test_service_registry import contract
from models.component_conversion_plan import ComponentConversionPlan
from models.pipeline_configuration import PipelineConfiguration
from runtime.operation_reuse.dependency_reuse import PublishedDependencies
from runtime.operation_reuse.publication import snapshot_service
from tools.conversion_tools.dependency_planning.reuse_sources import component_input_identity, component_sources
from tools.shared_artifact_store.storage import ArtifactStore
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.service_api_uses import record_service_use


def test_component_candidates_require_matching_source_and_intact_bytes(tmp_path):
    profile = PipelineConfiguration(shared_store_root=str(tmp_path), source_workspace_id='bank')
    plan = ComponentConversionPlan(components={'base': dict(component_id='base', kind='java_implementation',
        label='example.Base', status='source_recorded', operations=['WEB/A'], provenance=dict(source_hash='original', source_project='Core'))},
        groups=[dict(group_id='base-group', members=['base'], reason='Implementation')])
    assert component_sources(plan.model_dump(), profile)['base']['source'] == 'source'
    metadata = dict(validated=True, input_identity=component_input_identity(plan, plan.groups[0], profile),
        coordinates=dict(group_id='bank', artifact_id='base', version='1'))
    with ArtifactStore(tmp_path, 'components') as store:
        directory, _ = store.publish('base-key', {'artifact.jar': b'approved-jar'}, metadata)
    choice = component_sources(plan.model_dump(), profile)['base']
    assert choice['source'] == 'shared_component'
    assert choice['validation'] == 'current_scope_validation_pending'
    (tmp_path / 'components/registry.db').unlink()
    assert component_sources(plan.model_dump(), profile)['base']['source'] == 'shared_component'
    assert not (tmp_path / 'components/registry.db').exists()
    plan.components['base'].provenance['source_hash'] = 'changed'
    assert component_sources(plan.model_dump(), profile)['base']['source'] == 'source'
    plan.components['base'].provenance['source_hash'] = 'original'
    (directory / 'artifact.jar').write_bytes(b'corrupt')
    assert component_sources(plan.model_dump(), profile)['base']['source'] == 'source'


def test_api_boundary_recovers_read_only_without_original_run_or_registry(tmp_path, contract):
    profile = PipelineConfiguration(shared_store_root=str(tmp_path / 'shared'), source_workspace_id='bank')
    run = tmp_path / 'run'
    native = run / 'standalone'
    native.mkdir(parents=True)
    (native / 'Example.java').write_text('class Example {}')
    report = run / 'approved.md'
    report.write_text('Approved')
    record = deepcopy(contract)
    (run / 'service.jar').write_bytes(b'approved-package')
    record['api_definition']['artifact_evidence'] = dict(root=str(run), files={
        'service.jar': hashlib.sha256(b'approved-package').hexdigest()})
    record['completion']['validation_report_reference'] = str(report)
    snapshot_service(profile, run, native, record)
    (tmp_path / 'shared/operations/registry.db').unlink()
    (native / 'Example.java').unlink()
    report.unlink()
    with PublishedDependencies(profile) as registry:
        service = registry.lookup('WEB/GetLinks')
        assert service is not None and service.path == '/links'
        assert registry.lookup('OTHER/GetLinks') is None
    assert not (tmp_path / 'shared/operations/registry.db').exists()


def test_automatic_api_pin_preserves_outer_transaction(contract):
    conn = get_connection(':memory:')
    conn.execute('CREATE TABLE changes(value TEXT)')
    conn.execute("INSERT INTO changes VALUES ('pending')")
    record_service_use(conn, 'run', contract, 'test')
    conn.rollback()
    assert conn.execute('SELECT count(*) FROM changes').fetchone()[0] == 0
    conn.close()
