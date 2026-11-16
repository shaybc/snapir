"""Classify original binary availability separately from the AI-selected native dependencies."""

import hashlib
from pathlib import Path
from zipfile import ZipFile
from models.maven_dependency import MavenDependency
from models.retained_library import RetainedLibrary
from tools.conversion_tools.composer_runtime_contracts import composer_class, documented_contract
from tools.maven_dependency_tools.jar_metadata import archive_coordinates


def candidate_record(name, origin, detail, *, locations=()):
    """Keep unrelated supporting imports visible without declaring them required target code."""
    return dict(class_name=name, treatment='candidate', maven_coordinates=None, behavior_description='',
                behavior_evidence=[], origin=origin, scope='source_evidence_only', detail=detail, locations=list(locations))


def retained_record(name, location, profile, origin, rule=None):
    """Require actual class ownership and original IBM approval before proposing retention."""
    if composer_class(name):
        raise ValueError('Composer runtime must be replaced, not retained: ' + name)
    path = Path(location.removeprefix('jar:')).resolve()
    with ZipFile(path) as archive:
        if name.replace('.', '/') + '.class' not in archive.namelist() and not any(
            item[:-6].replace('/', '.').replace('$', '.') == name for item in archive.namelist() if item.endswith('.class')):
            raise ValueError('Retained archive does not contain required class: ' + name)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    coordinates = archive_coordinates(path)
    explicit = rule.get('maven_coordinates') if rule else None
    if explicit:
        if coordinates and explicit != ':'.join(coordinates):
            raise ValueError('Explicit retained coordinates disagree with original archive metadata: ' + name)
        coordinates = tuple(explicit.split(':'))
    original = ':'.join(coordinates) if coordinates else None
    ibm = name.startswith('com.ibm.')
    if ibm and name not in getattr(profile, 'allowed_ibm_classes', ()) and original not in getattr(profile, 'allowed_ibm_artifacts', ()):
        raise ValueError('IBM client library requires a configured class or artifact exception: ' + name)
    group, artifact, version = coordinates or ('snapir.retained', 'jar-' + digest[:24], '1-' + digest[24:40])
    if not explicit and version.upper().endswith('-SNAPSHOT'):
        group, artifact, version = 'snapir.retained', 'jar-' + digest[:24], '1-' + digest[24:40]
    dependency = MavenDependency(group_id=group, artifact_id=artifact, version=version, scope='compile',
                                reason='Original verified library; use only if required by generated native code', required_classes=[name])
    sidecar = path.with_suffix('.pom')
    pom_hash = None
    if sidecar.is_file():
        with sidecar.open('rb') as stream:
            pom_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    library = RetainedLibrary(path=str(path), sha256=digest, dependency=dependency, original_coordinates=original, ibm=ibm, pom_sha256=pom_hash)
    return dict(class_name=name, treatment='retain', maven_coordinates=dependency.coordinates,
                behavior_description='', behavior_evidence=[], origin=origin, scope='source_evidence_candidate',
                library=library.model_dump(mode='json'))


def composer_record(name, origin):
    """Use specific documentation as replacement evidence when implementation source is absent."""
    evidence = documented_contract(name)
    if not evidence:
        return None
    return dict(class_name=name, treatment='replace', maven_coordinates=None, origin=origin,
                behavior_description='Replace documented Composer behavior with native code', behavior_evidence=evidence)


def dependency_record(name, rules, profile, origin, classpath, *, source_exists=False, required=False):
    """Resolve overrides and verified libraries; unavailable supporting imports remain candidates."""
    from tools.conversion_tools.external_dependency_resolver import external_dependency
    explicit = external_dependency(name, rules, None, origin)
    if explicit and explicit['treatment'] == 'replace':
        return explicit
    if composer_class(name) and explicit and explicit['treatment'] == 'retain':
        raise ValueError('Composer runtime must be replaced, not retained: ' + name)
    if source_exists and not explicit:
        return None
    if composer_class(name):
        documented = composer_record(name, origin)
        if documented:
            return documented
    locations = classpath.classes.get(name, []) if classpath is not None else []
    selection = next((item for item in getattr(classpath, 'binary_resolutions', []) if item['class_name'] == name), None)
    if len(locations) == 1 and locations[0].startswith('jdk:'):
        return None
    if len(locations) == 1 and locations[0].startswith('jar:') and not composer_class(name):
        try:
            record = retained_record(name, locations[0], profile, origin, explicit)
            if selection:
                record['binary_resolution'] = selection
            return record
        except ValueError as exc:
            if required:
                raise
            return candidate_record(name, origin, str(exc), locations=locations)
    detail = ('Composer behavior lacks documentation and project source: ' if composer_class(name) else
              'Dependency has no unique verified library or source origin: ') + name
    if selection and selection['status'] == 'unestablished_container_order':
        detail += ' | Container order is not established for project ' + str(selection['project']) + '; configure eclipse_project_classpath_containers'
    if required and composer_class(name):
        raise ValueError(detail)
    if not required:
        record = candidate_record(name, origin, detail, locations=locations)
        if selection:
            record['binary_resolution'] = selection
        return record
    return None
