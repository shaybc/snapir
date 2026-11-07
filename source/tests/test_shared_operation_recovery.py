"""Recover approved API contracts and artifacts without their original conversion run."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from test_service_registry import contract
from models.pipeline_configuration import PipelineConfiguration
from runtime.operation_reuse.publication import snapshot_service
from tools.converted_service_registry_tools.registry import open_registry, get_service, publish_service


def test_service_registry_recovers_from_durable_operation_artifacts(tmp_path, contract):
    profile = PipelineConfiguration(shared_store_root=str(tmp_path / 'shared'), source_workspace_id='bank')
    run = tmp_path / 'disposable-run'
    native = run / 'WEB/GetLinks/standalone'
    (native / 'src/main/java').mkdir(parents=True)
    (native / 'src/main/java/Example.java').write_text('class Example {}')
    (run / 'service.jar').write_bytes(b'approved-package')
    report = run / 'report.md'
    report.write_text('Approved final validation')
    import hashlib
    record = deepcopy(contract)
    record['schema_version'] = 'v2'
    record['api_definition']['artifact_evidence'] = dict(root=str(run), files={
        'service.jar': hashlib.sha256(b'approved-package').hexdigest()})
    record['completion']['validation_report_reference'] = str(report)
    archived = snapshot_service(profile, run, native, record)
    database = tmp_path / 'shared/operations/registry.db'
    registry = open_registry(database)
    publish_service(registry, archived)
    first = get_service(registry, 'bank', 'WEB', 'GetLinks')
    registry.close()
    assert run.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(run)
    database.unlink()
    registry = open_registry(database)
    try:
        restored = get_service(registry, 'bank', 'WEB', 'GetLinks')
        assert restored.api_revision == first.api_revision
        assert restored.implementation_revision == first.implementation_revision
        assert Path(restored.artifact_reference).is_dir()
        assert Path(restored.completion.validation_report_reference).is_file()
    finally:
        registry.close()


def test_v2_registry_paths_survive_shared_store_relocation(tmp_path, contract):
    root = tmp_path / 'original/operations'
    registry = open_registry(root / 'registry.db')
    record = deepcopy(contract)
    record.update(schema_version='v2', artifact_reference=str(root / 'artifacts/example/project'))
    record['completion']['validation_report_reference'] = str(root / 'artifacts/example/report.md')
    publish_service(registry, record)
    saved = json.loads(registry.execute('SELECT contract_json FROM converted_operation_services').fetchone()[0])
    assert saved['artifact_reference'] == 'artifacts/example/project'
    registry.close()
    moved = tmp_path / 'relocated'
    root.parent.rename(moved)
    registry = open_registry(moved / 'operations/registry.db')
    try:
        restored = get_service(registry, 'bank', 'WEB', 'GetLinks')
        assert restored.artifact_reference == str(moved / 'operations/artifacts/example/project')
    finally:
        registry.close()


def test_new_implementation_and_host_do_not_change_a_pinned_api(tmp_path, contract):
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.service_api_uses import record_service_use, get_service_use
    from tools.operation_call_tools.published_calls import call_contract
    first = deepcopy(contract)
    first.update(schema_version='v2', implementation_revision='implementation-one')
    registry = open_registry(tmp_path / 'registry.db')
    run = get_connection(':memory:')
    try:
        first = publish_service(registry, first)
        pinned = record_service_use(run, 'first-run', first, 'test')
        second = first.model_dump(mode='json')
        second['implementation_revision'] = 'implementation-two'
        second['artifact_reference'] = 'new-project'
        second['addresses']['test']['base_url'] = 'https://another.example'
        second = publish_service(registry, second)
        other = record_service_use(run, 'second-run', second, 'test')
        assert second.api_revision == first.api_revision
        assert call_contract(pinned)['fingerprint'] == call_contract(other)['fingerprint']
        assert get_service_use(run, 'first-run', 'bank', 'WEB', 'GetLinks').contract.implementation_revision == 'implementation-one'
    finally:
        run.close()
        registry.close()


def test_known_new_environment_does_not_require_a_deployment_record(tmp_path, contract):
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.service_api_uses import record_service_use
    from runtime.service_addresses import service_url
    profile = PipelineConfiguration(deployment_environment='production', service_environments={
        'production': dict(namespace='bank-production', external_url_pattern='https://{service_name}.apps.example')})
    conn = get_connection(':memory:')
    try:
        use = record_service_use(conn, 'production-caller', contract, 'production', profile=profile)
        assert service_url(use.address, 'microservice') == 'http://web-getlinks.bank-production.svc.cluster.local:8080'
    finally:
        conn.close()


def test_legacy_json_without_new_optional_fields_remains_idempotent(tmp_path, contract):
    from tools.state_store_tools.db import get_connection
    from tools.state_store_tools.service_api_uses import record_service_use
    registry = open_registry(tmp_path / 'legacy.db')
    conn = get_connection(':memory:')
    try:
        registry.execute('INSERT INTO converted_operation_services VALUES (?,?,?,?,?,?)',
            ('bank','WEB','GetLinks','1',json.dumps(contract),'2026-01-01'))
        registry.commit()
        published = publish_service(registry, contract)
        use = record_service_use(conn, 'saved-run', published, 'test')
        legacy = use.model_dump(mode='json')
        legacy['contract'].pop('implementation_revision')
        for address in [legacy['address'], *legacy['contract']['addresses'].values()]:
            for field in ('internal_base_url','external_base_url','service_name','namespace'):
                address.pop(field, None)
        conn.execute('UPDATE service_api_uses SET use_json=?', (json.dumps(legacy),))
        conn.commit()
        assert record_service_use(conn, 'saved-run', published, 'test') == use
    finally:
        conn.close()
        registry.close()
