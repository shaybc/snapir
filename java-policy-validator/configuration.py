"""Merge the common converter defaults with this validator's explicit local settings."""
from pathlib import Path
import yaml
from common_configuration import load_common

ROOT = Path(__file__).resolve().parent
FIELDS = {'java_version', 'java_home', 'maven_settings_path', 'maven_local_repository'}


def load(path, common_config=None, *, overrides=None):
    """Resolve local YAML paths locally; explicit CLI inputs take precedence over both YAML files."""
    path = Path(path).resolve()
    try:
        supplied = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    except yaml.YAMLError as error:
        raise ValueError('Invalid validator configuration YAML: ' + str(path)) from error
    if not isinstance(supplied, dict) or set(supplied) - FIELDS - {'common_config_path', 'target_java_version'}:
        raise ValueError('Validator configuration must contain only documented settings')
    configured = supplied.get('common_config_path')
    if configured:
        if not isinstance(configured, str):
            raise ValueError('common_config_path must be a YAML path or null')
        configured = str((path.parent / Path(configured).expanduser()).resolve())
    # Resolve local path values before merging CLI values, whose paths are relative to the caller.
    local = dict(supplied)
    for key in ('java_home', 'maven_settings_path', 'maven_local_repository'):
        if local.get(key):
            if not isinstance(local[key], str):
                raise ValueError(key + ' must be a path or null')
            local[key] = str((path.parent / Path(local[key]).expanduser()).resolve())
    local.update(overrides or {})
    settings = load_common(ROOT, common_config, configured, overrides=local, override_base=Path.cwd())
    settings['target_java_version'] = local['target_java_version'] if 'target_java_version' in local else settings['java_version']
    if type(settings['target_java_version']) is not int or settings['target_java_version'] < 17:
        raise ValueError('target_java_version must be an integer of at least 17')
    return settings
