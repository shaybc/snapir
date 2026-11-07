"""Carry Gate-2-approved managed source implementations into later conversion runs."""
import json
from pathlib import Path
from xml.etree import ElementTree

from tools.shared_artifact_store.location import store_root, application_id
from tools.shared_artifact_store.manifests import content_hash, file_hash
from tools.shared_artifact_store.storage import ArtifactStore


def managed_identity(data, profile):
    """Match original behavior and converted dependency APIs without run-local library placement."""
    dependencies = [{name: value for name, value in item.items() if name not in {'library_id', 'project', 'source_path'}}
                    for item in data.get('converted_dependency_apis', [])]
    return 'managed-' + content_hash(dict(application=application_id(profile), kind=data['kind'],
        source=data['primary_source_content'], source_hash=data.get('source_component_hash'),
        dependency_source=data.get('dependency_source_hash'), dependencies=dependencies,
        external=data.get('external_dependencies', []), evidence=data.get('composer_behavior_evidence', []),
        configuration=data.get('relationship_context') if data.get('managed_project_operation') else None,
        java_version=profile.java_version, allowed_classes=profile.allowed_ibm_classes,
        allowed_artifacts=profile.allowed_ibm_artifacts, policy='managed-class-shared-v1'))


def publish_managed_component(profile, item):
    """Preserve reviewed source and dependency declarations only after the existing Gate 2 accepts it."""
    if not getattr(profile, 'cross_run_component_reuse', True):
        return
    source = Path(item['source_path'])
    if file_hash(source) != item['source_hash']:
        raise ValueError('Approved managed source changed before shared publication')
    project = Path(item['project'])
    relative = source.resolve().relative_to((project / 'src/main/java').resolve()).as_posix()
    pom = project / 'pom.xml'
    if file_hash(pom) != item['pom_hash']:
        raise ValueError('Approved managed POM changed before shared publication')
    dependencies = []
    for node in ElementTree.parse(pom).getroot().findall('{*}dependencies/{*}dependency'):
        values = [node.findtext('{*}' + name) for name in ('groupId', 'artifactId', 'version')]
        if all(values):
            dependencies.append(dict(group_id=values[0], artifact_id=values[1], version=values[2],
                                     scope=node.findtext('{*}scope') or 'compile', reason='Approved managed component dependency'))
    key = managed_identity(item['task_input'], profile)
    with ArtifactStore(store_root(profile), 'components') as store:
        store.publish(key, {'source/' + relative: source, 'evidence/pom.xml': pom},
                      dict(validated=True, gate=2, source=relative, dependencies=dependencies))


def restore_managed_component(conn, config, profile, data, context):
    """Restore exact approved source into the current project for its normal compile and review."""
    if not getattr(profile, 'cross_run_component_reuse', True):
        return None
    key = managed_identity(data, profile)
    with ArtifactStore(store_root(profile), 'components') as store:
        found = store.find(key)
        if found is None:
            return None
        directory, manifest = found
        metadata = manifest['metadata']
        from tools.shared_artifact_store.manifests import contained_path
        target = contained_path(context.source_root, metadata['source'])
        source = contained_path(directory, 'source/' + metadata['source'])
        if target.exists() and file_hash(target) != file_hash(source):
            return None
        from models.maven_dependency import MavenDependency
        from tools.maven_dependency_tools.pom_manager import merge_dependencies
        from runtime.dependency_policy import canonical_dependencies
        from constants import COMMON_LIB_GROUP_ID
        current = {(node.findtext('{*}groupId'), node.findtext('{*}artifactId')): node.findtext('{*}version')
                   for node in ElementTree.parse(context.pom_path).getroot().findall('{*}dependencies/{*}dependency')}
        dependencies = canonical_dependencies(profile, metadata['dependencies'], historical=True)
        for dependency in dependencies:
            if dependency.group_id == COMMON_LIB_GROUP_ID:
                version = current.get((dependency.group_id, dependency.artifact_id))
                if not version:
                    return None
                dependency.version = version
        merge_dependencies(context.pom_path, dependencies,
                           context.verifier, allowed_ibm_artifacts=context.allowed_ibm_artifacts, task_id='shared-managed-component')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        from tools.state_store_tools.component_reuse import record_component_use
        record_component_use(conn, config.run_id, config.output_root, key, manifest)
        return dict(source_path=str(target), java_source=target.read_text(encoding='utf-8'))
