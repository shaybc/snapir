"""Preserve approved operation deliveries outside the run that produced them."""
from copy import deepcopy
import json
from pathlib import Path

from runtime.operation_layout import operation_repository
from tools.shared_artifact_store.location import store_root
from tools.shared_artifact_store.locking import artifact_lock
from tools.shared_artifact_store.manifests import contained_path, content_hash
from tools.shared_artifact_store.storage import ArtifactStore


def snapshot_service(profile, directory, native_project, contract):
    """Archive the approved project and delivery evidence; keep paths relative in saved metadata."""
    directory = Path(directory).resolve()
    repository = operation_repository(native_project).resolve()
    files = {}
    for path in repository.rglob('*'):
        relative = path.relative_to(repository)
        if any(part in {'.git', '.demo-runtime', 'target', '__pycache__'} or part.endswith('.PKG') for part in relative.parts):
            continue
        if path.is_file() and path.name not in {'runtime-config.json', '.env'}:
            files['project/' + relative.as_posix()] = path
    evidence = contract['api_definition']['artifact_evidence']
    for name in evidence['files']:
        normalized = name.replace('\\', '/')
        files['delivery/' + normalized] = contained_path(directory, normalized)
    report = Path(contract['completion']['validation_report_reference'])
    if report.is_file():
        files['evidence/final_report.md'] = report
    record = deepcopy(contract)
    record['artifact_reference'] = 'project'
    record['api_definition']['artifact_evidence']['root'] = 'delivery'
    record['api_definition']['artifact_evidence']['files'] = {name.replace('\\', '/'): value for name, value in evidence['files'].items()}
    record['completion']['validation_report_reference'] = 'evidence/final_report.md'
    key = content_hash([record['application_id'], record['channel'], record['operation_id']])
    from tools.state_store_tools._json import utc_now
    with artifact_lock(store_root(profile), ['operation', key]):
        with ArtifactStore(store_root(profile), 'operations') as store:
            path, manifest = store.publish(key, files, dict(validated=True, standalone_validated=True,
                microservice_validated=True, api_published=True, published_at=utc_now(), service_contract=record))
    return materialize_contract(path, manifest)


def materialize_contract(directory, manifest):
    """Resolve stored relative references at the current store location."""
    record = deepcopy(manifest['metadata']['service_contract'])
    record['artifact_reference'] = str(contained_path(directory, record['artifact_reference']))
    record['api_definition']['artifact_evidence']['root'] = str(contained_path(directory, record['api_definition']['artifact_evidence']['root']))
    record['completion']['validation_report_reference'] = str(contained_path(directory, record['completion']['validation_report_reference']))
    record['implementation_revision'] = manifest['revision']
    return record
