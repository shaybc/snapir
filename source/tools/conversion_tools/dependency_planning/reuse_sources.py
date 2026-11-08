"""Expose source/artifact choices during preparation without generating or accepting code."""
import sqlite3
from contextlib import closing

from models.component_conversion_plan import ComponentConversionPlan
from runtime.component_conversion.shared_identity import implementation_identity, neutral_group
from tools.shared_artifact_store.location import store_root, application_id
from tools.shared_artifact_store.manifests import content_hash, contained_path, read_manifest


def component_input_identity(plan, group, profile):
    """Bind reuse candidates to the application, complete source resolution and target policy."""
    return dict(application_id=application_id(profile), java_version=profile.java_version,
        implementation=implementation_identity(plan, group, profile))


def component_sources(value, profile):
    """Describe each needed node and folded source; artifact hits remain subject to execution checks."""
    plan = ComponentConversionPlan.model_validate(value)
    choices = {}
    for key, node in plan.components.items():
        choices[key] = dict(kind=node.kind, logical_id=node.label, required_by=node.operations,
            source='source' if node.kind == 'java_implementation' else 'configuration' if node.kind in {
                'configured_step', 'format_composition', 'format_node'} else 'classpath' if node.kind == 'external_dependency' else
                'service_contract' if node.kind == 'operation_contract' else 'unresolved',
            source_project=node.provenance.get('source_project'), source_file=node.provenance.get('source_file'),
            source_hash=node.provenance.get('source_hash'), dependencies=node.dependencies)
        for source in node.provenance.get('supporting_sources', []):
            identity = source.get('definition_id')
            if identity:
                entry = choices.setdefault('supporting:' + identity, dict(kind='supporting_source', logical_id=source['fqcn'],
                    source='source', required_by=[], included_in=[], source_file=source.get('source_file'), source_hash=source.get('source_hash')))
                entry['included_in'] = sorted(set(entry['included_in']) | {key})
                entry['required_by'] = sorted(set(entry['required_by']) | set(node.operations))
    if not getattr(profile, 'cross_run_component_reuse', True):
        return choices
    directory = store_root(profile) / 'components'
    candidates = _manifests(directory)
    for group in plan.groups:
        if not neutral_group(plan, group):
            continue
        expected = component_input_identity(plan, group, profile)
        for path, manifest in candidates:
            if manifest['metadata'].get('input_identity') != expected:
                continue
            try:
                verified = read_manifest(path)
            except (OSError, ValueError, KeyError):
                continue
            for key in group.members:
                choices[key].update(source='shared_component', artifact_key=verified['lookup_key'],
                    artifact_revision=verified['revision'], coordinates=verified['metadata']['coordinates'],
                    validation='current_scope_validation_pending')
            break
    return choices


def _manifests(directory):
    """Read indexed candidates or recover a missing index from immutable manifests, without writes."""
    database = directory / 'registry.db'
    paths = []
    if database.is_file():
        try:
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone():
                    for (name,) in conn.execute('SELECT path FROM artifacts ORDER BY rowid DESC'):
                        try:
                            paths.append(contained_path(directory, name))
                        except ValueError:
                            continue
        except sqlite3.DatabaseError:
            paths = []
    if not paths:
        paths = sorted((path.parent for path in (directory / 'artifacts').glob('*/*/manifest.json')), reverse=True)
    result = []
    for path in paths:
        try:
            result.append((path, read_manifest(path, verify=False)))
        except (OSError, ValueError, KeyError):
            continue
    return result
