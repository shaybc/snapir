"""Move saved operation projects without regenerating Java or rewriting request/attempt history."""
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from runtime.operation_state_relocation import rebind_current_artifacts


def source_inventory(project):
    """Fingerprint native or wrapper sources and their POM before any filesystem changes."""
    project = Path(project)
    return {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [project/'pom.xml', *project.joinpath('src').rglob('*')] if p.is_file()}


def verify_inventory(project, expected):
    """Reject altered, missing or added source files after relocation."""
    if source_inventory(project) != expected:
        raise ValueError('Project sources or POM changed during layout migration')


def migrate_operation(conn, config, channel, operation, directory, audit):
    """Preserve backup/state history, move the two projects, and verify their unchanged source bytes.

    All targets are resolved inside the explicitly selected run. A failure retains
    the checkpoint backup and audit data; it never deletes user directories.
    The caller must perform fresh build/Helm validation and bind new Gate 4/5 reports.
    """
    directory, audit = Path(directory).resolve(), Path(audit).resolve()
    repository = (Path(config.output_root)/channel/operation).resolve()
    old_service = (directory/'services'/channel/operation).resolve()
    if not repository.is_relative_to(directory) or not old_service.is_relative_to(directory):
        raise ValueError('Migration projects must stay inside the selected run')
    if repository.is_symlink() or old_service.is_symlink() or audit.is_relative_to(repository):
        raise ValueError('Migration cannot follow external links or store backups inside the deliverable')
    if not (repository/'pom.xml').is_file() or (repository/'standalone/pom.xml').exists():
        raise ValueError('Select an unmigrated native operation project')
    if not (old_service/'pom.xml').is_file():
        raise ValueError('Saved microservice project is missing')
    current=conn.execute('SELECT status FROM runs WHERE run_id=?',(config.run_id,)).fetchone()
    if current is None or current['status']=='in_progress':raise ValueError('Stop the saved run before migrating its projects')
    audit.mkdir(parents=True, exist_ok=True)
    backup = audit/'before-layout.sqlite'
    if backup.exists():
        raise ValueError('Migration audit already exists; do not repeat filesystem moves')
    target = sqlite3.connect(backup)
    conn.backup(target); target.close()
    native_hashes, service_hashes = source_inventory(repository), source_inventory(old_service)
    (audit/'source-before.json').write_text(json.dumps(dict(native=native_hashes, service=service_hashes), indent=2))
    binding = json.loads((repository/'standalone/operation.json').read_text(encoding='utf-8'))
    runtime = (repository/'standalone'/binding['runtime_config']).resolve()
    holding = audit/'native-relocation'
    if holding.exists():
        raise ValueError('Relocation holding directory already exists')
    native = repository/'standalone'
    root = repository/'microservice'
    application = root/'application'
    service_copied=False
    repository.rename(holding)
    try:
        repository.mkdir()
        holding.rename(native)
        root.mkdir()
        try:
            old_service.rename(application)
        except PermissionError:
            # A Windows directory handle can prevent rename while all files remain readable.
            # Keep that original outside the deliverable as an additional backup, never delete it.
            if any(p.is_symlink() for p in old_service.rglob('*')):
                raise ValueError('Saved service contains an external link')
            shutil.copytree(old_service,application)
            service_copied=True
        verify_inventory(native, native_hashes);verify_inventory(application, service_hashes)
    except BaseException:
        if application.exists():
            if old_service.exists():application.rename(audit/'failed-application-copy')
            else:application.rename(old_service)
        if native.exists():native.rename(holding)
        if root.exists():root.rmdir()
        repository.rmdir();holding.rename(repository)
        raise
    conn.execute('SAVEPOINT operation_layout_relocation')
    try:
        changes = rebind_current_artifacts(conn, config.run_id, [(repository, native), (old_service, application)])
        conn.execute("UPDATE generated_artifacts SET generated_path=? WHERE run_id=? AND artifact_kind='service' AND generated_path=?",
            (str(root), config.run_id, str(old_service)))
        conn.execute('RELEASE SAVEPOINT operation_layout_relocation');conn.commit()
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT operation_layout_relocation')
        conn.execute('RELEASE SAVEPOINT operation_layout_relocation')
        # Only undo the exact moves above; rmdir refuses any unexpected user files.
        if service_copied:application.rename(audit/'failed-application-copy')
        else:application.rename(old_service)
        native.rename(holding)
        root.rmdir();repository.rmdir();holding.rename(repository)
        raise
    from runtime.behavior_conversion.standalone_runner import write_standalone_runner
    from types import SimpleNamespace
    write_standalone_runner(native, config.output_root, SimpleNamespace(service_api=SimpleNamespace(type_name=binding['service_class'])))
    archive_legacy_packaging(native,audit)
    # The existing demo definition and original fixture bytes are reused, not generated again.
    from runtime.fixture_demo.preparation import prepare_operation_demo
    demo = prepare_operation_demo(native, config.output_root, channel+'/'+operation)
    if demo['status'] != 'prepared':
        raise ValueError('Relocated demo preparation failed: '+'; '.join(demo['issues']))
    path=native/'standalone/operation.json';updated=json.loads(path.read_text(encoding='utf-8'))
    updated['runtime_config']=os.path.relpath(runtime,path.parent).replace('\\','/')
    path.write_text(json.dumps(updated,indent=2)+'\n',encoding='utf-8')
    # Keep previously generated converter records outside the new source repository.
    from runtime.operation_layout import service_artifacts
    records=service_artifacts(root);records.mkdir(parents=True,exist_ok=True)
    for name in ['dependency_audit.jsonl','deployment-readiness.json','image-variants.json','microservice-package.json','images']:
        source=application/name
        if source.exists():
            destination=records/('previous-'+name)
            if destination.exists():raise ValueError('Existing audit destination: '+str(destination))
            source.rename(destination)
    if (application/'helm').exists():
        (application/'helm').rename(root/'helm')
        for name in ['helm-validation.json','schema-cache']:
            source=root/'helm'/name
            if source.exists():source.rename(records/('previous-'+name))
    for name in ['Dockerfile','.dockerignore']:
        source=application/name
        if source.exists():source.rename(root/name)
    verify_inventory(native,native_hashes);verify_inventory(application,service_hashes)
    result=dict(repository=str(repository),standalone=str(native),microservice=str(root),application=str(application),
        source_bytes_unchanged=True,state_relocations=changes,demo=demo['status'],backup=str(backup),
        generation_attempts_reset=False,native_regenerated=False,deployed=False,
        legacy_service_backup_retained=service_copied)
    (audit/'relocation.json').write_text(json.dumps(result,indent=2))
    return result


def archive_legacy_packaging(native,audit):
    """Retain the former root batch/distribution as history, outside the migrated repository."""
    native,audit=Path(native).resolve(),Path(audit).resolve()
    if native.name!='standalone' or audit.is_relative_to(native.parent):
        raise ValueError('Legacy packaging archive must be outside the operation repository')
    for source in [native/'package-standalone-operation.bat',native/(native.parent.name+'.PKG')]:
        if source.exists():
            if source.is_symlink() or not source.resolve().is_relative_to(native):
                raise ValueError('Legacy packaging source escaped the migrated native project')
            target=audit/('previous-'+source.name)
            if target.exists():raise ValueError('Legacy packaging archive already exists')
            source.rename(target)
