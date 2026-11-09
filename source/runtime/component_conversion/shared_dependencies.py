"""Replace shared neutral source copies with pinned JARs in final configured units."""
import json
from pathlib import Path
import shutil
from xml.etree import ElementTree

from models.maven_dependency import MavenDependency
from tools.shared_artifact_store.location import store_root
from tools.shared_artifact_store.storage import ArtifactStore
from tools.shared_artifact_store.maven import install_artifact, repository_files
from tools.state_store_tools.component_reuse import group_uses


def attach_shared_components(conn, config, profile, plan, needed, files, report):
    """Honor current sharing thresholds; local components still benefit from saved generation."""
    uses = group_uses(conn, config.run_id)
    if not uses:
        return files, report, []
    minimum = getattr(profile, 'shared_library_min_usage', 5)
    selected = []
    class_owners = {}
    logical_owners = {}
    global_consumers = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='shared_component_consumers'").fetchone():
        global_consumers = {row[0]: json.loads(row[1]) for row in conn.execute(
            'SELECT group_id,consumers_json FROM shared_component_consumers WHERE run_id=?', (config.run_id,))}
    with ArtifactStore(store_root(profile), 'components') as store:
        for group in plan.groups:
            if group.group_id not in needed or group.group_id not in uses:
                continue
            consumers = {name for member in group.members for name in plan.components[member].operations}
            consumers.update(global_consumers.get(group.group_id, []))
            if len(consumers) < minimum:
                continue
            manifest = uses[group.group_id]
            found = store.find(manifest['lookup_key'], revision=manifest['revision'])
            if found is None:
                from runtime.component_conversion.shared_recovery import restore_from_run
                found = restore_from_run(store, conn, config, group.group_id, manifest)
            if found is None:
                raise ValueError('Pinned shared component disappeared; restore it before packaging')
            directory, manifest = found
            for name, owners in [(name, class_owners) for name in manifest['metadata'].get('classes', [])] + [
                    (name, logical_owners) for name in manifest['metadata'].get('logical_components', [])]:
                if name in owners and owners[name] != manifest['revision']:
                    raise ValueError('Conflicting shared component versions for ' + name)
                owners[name] = manifest['revision']
            install_artifact(directory, manifest, profile)
            selected.append(manifest)
            files = {name: text for name, text in files.items() if name not in manifest['metadata']['owned_sources']}
    report = dict(report)
    report['dependencies'] = [*report['dependencies'], *[MavenDependency(**item['metadata']['coordinates'],
        reason='Pinned cross-run shared component').model_dump(mode='json') for item in selected]]
    return files, report, [dict(key=item['lookup_key'], revision=item['revision']) for item in selected]


def materialize_operation_dependencies(conn, config, profile, project):
    """Bundle generated dependency artifacts beside an operation without storing absolute paths."""
    uses = group_uses(conn, config.run_id)
    if not uses:
        return
    project = Path(project)
    if not (project / 'pom.xml').is_file():
        return
    declared = {(node.findtext('{*}groupId'), node.findtext('{*}artifactId'), node.findtext('{*}version'))
                for node in ElementTree.parse(project / 'pom.xml').getroot().findall('{*}dependencies/{*}dependency')}
    pending = [item for item in uses.values() if 'coordinates' in item['metadata'] and
               tuple(item['metadata']['coordinates'][field] for field in ('group_id','artifact_id','version')) in declared]
    if not pending:
        return
    destination = project / 'shared-dependencies'
    records = []
    seen = set()
    with ArtifactStore(store_root(profile), 'components') as store:
        while pending:
            manifest = pending.pop()
            if manifest['revision'] in seen:
                continue
            seen.add(manifest['revision'])
            found = store.find(manifest['lookup_key'], revision=manifest['revision'])
            if found is None:
                raise ValueError('Cannot package a missing pinned component')
            directory, verified = found
            retained = verified['metadata'].get('retained_dependencies')
            if retained:
                from runtime.retained_libraries.artifacts import restore_portable
                from tools.shared_artifact_store.manifests import contained_path
                restore_portable(contained_path(directory, retained), project / 'retained-dependencies')
            for name, source in repository_files(directory, verified).items():
                target = destination / 'repository' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            source_copy = destination / 'components' / verified['revision']
            shutil.copytree(directory, source_copy, dirs_exist_ok=True)
            records.append(dict(key=verified['lookup_key'], revision=verified['revision'],
                                coordinates=verified['metadata']['coordinates']))
            for dependency in verified['metadata'].get('generated_dependencies', []):
                saved = store.find(dependency['key'], revision=dependency['revision'])
                if saved is None:
                    raise ValueError('Transitive shared component is unavailable')
                pending.append(saved[1])
    manifest_path = destination / 'dependencies.lock.json'
    if (project / 'retained-dependencies').exists():
        from tools.shared_artifact_store.project_repository import attach_repository
        attach_repository(project / 'pom.xml', (), retained=True)
    manifest_path.write_text(json.dumps(dict(schema_version=1, components=sorted(records,key=lambda item:item['key'])), indent=2) + '\n', encoding='utf-8')
