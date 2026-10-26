"""Version the conversion facts that determine scoped reuse compatibility."""

import hashlib
import json
from pathlib import Path

from tools.composer_mapper_tools.scoped_intake_evidence import file_digest

POLICY_VERSION = 'scoped-v3-c8-v1'


def digest(value):
    """Hash JSON facts deterministically, independent of dictionary insertion order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def revision(path):
    """Represent absent inputs explicitly; never treat a missing file as unchanged."""
    try:
        return file_digest(path)
    except OSError:
        return None


def conversion_policy(profile):
    """Fingerprint relevant generation/origin policy without persisting credentials."""
    names = ('conversion_strategy', 'scoped_native_mode', 'source_workspace_id', 'scoped_java_project', 'scoped_java_projects', 'java_version', 'java_home', 'classpath_jars',
        'eclipse_classpath_variables', 'allowed_ibm_artifacts', 'allowed_ibm_classes', 'external_dependencies',
        'conversion_requirements', 'maven_settings_path', 'maven_local_repository',
        'approved_maven_repository_urls', 'service_maven_dependencies')
    values = {}
    for name in names:
        value = getattr(profile, name, None)
        if isinstance(value, list):
            value = [item.model_dump(mode='json') if hasattr(item, 'model_dump') else item for item in value]
        elif isinstance(value, dict):
            value = {key: [item.model_dump(mode='json') if hasattr(item, 'model_dump') else item for item in items]
                     if isinstance(items, list) else items for key, items in value.items()}
        values[name] = value
    files = {str(Path(path).resolve()): revision(path) for path in getattr(profile, 'classpath_jars', ())}
    for name in ('maven_settings_path', 'composer_behavior_document'):
        path = getattr(profile, name, None)
        if path:
            files[str(Path(path).resolve())] = revision(path)
    from runtime.behavior_conversion.testing_contract import testing_contract
    testing = testing_contract(profile) if hasattr(profile, 'java_version') else None
    return digest(dict(version=POLICY_VERSION, settings=values, policy_files=files, testing=testing))


def classpath_fingerprint(index):
    """Include archive bytes, not only class names or archive paths."""
    locations = {location[4:] for entries in index.classes.values() for location in entries
                 if location.startswith(('jar:', 'jdk:'))}
    locations.update(index.libraries)
    return digest(dict(index=index.model_dump(mode='json'), archives={path: revision(path) for path in sorted(locations)}))
