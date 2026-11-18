"""Read the selected converter YAML only; never import another tool's application code."""
import os
from copy import deepcopy
from pathlib import Path
import yaml

# The converter's flat configuration names are the interchange contract.
SHARED_DEFAULTS = dict(source_root='./bank-demo/composer/Workspace', java_version=25, java_home=None,
    java_scan_inactivity_timeout_seconds=900, classpath_jars=[], framework_jars=[],
    eclipse_classpath_variables={}, eclipse_classpath_containers={}, eclipse_project_classpath_containers={},
    maven_settings_path=None, maven_local_repository=None, model_provider='gemini',
    model_name='gemini/gemini-3.5-flash-lite', model_base_url='', model_api_key_environment='GOOGLE_API_KEY',
    model_timeout_seconds=300, max_model_attempts=4)
SHARED_FIELDS = frozenset(SHARED_DEFAULTS)
PATH_FIELDS = ('source_root', 'java_home', 'maven_settings_path', 'maven_local_repository')


def select_common(tool_root, explicit=None, configured=None):
    """Select one YAML explicitly, through the environment, or from the repository root."""
    selected = explicit or os.environ.get('SNAPIR_COMMON_CONFIG') or configured
    if selected:
        path = Path(selected).expanduser().resolve()
        if not path.is_file():
            raise ValueError('Common converter configuration not found: ' + str(path))
        return path
    root = Path(tool_root).resolve().parent
    if (root / 'configs/default_config.yaml').is_file():
        return root / 'configs/default_config.yaml'
    if (root / 'config.yaml').is_file():
        return root / 'config.yaml'
    profiles = sorted({path.resolve() for folder in ('config', 'configs')
                       for pattern in ('*.yaml', '*.yml') for path in (root / folder).rglob(pattern) if path.is_file()})
    if len(profiles) == 1:
        return profiles[0]
    detail = '; available profiles: ' + ', '.join(map(str, profiles)) if profiles else ''
    raise ValueError('Select the converter YAML with --common-config, SNAPIR_COMMON_CONFIG, '
                     'or common_config_path in this tool config' + detail)


def load_common(tool_root, explicit=None, configured=None, *, overrides=None, override_base=None):
    """Apply explicit local overrides and resolve each shared path against the YAML supplying it."""
    path = select_common(tool_root, explicit, configured)
    try:
        supplied = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    except yaml.YAMLError as error:
        raise ValueError('Invalid YAML in common converter configuration: ' + str(path)) from error
    if not isinstance(supplied, dict):
        raise ValueError('Common converter configuration must be a YAML object: ' + str(path))
    result = deepcopy(SHARED_DEFAULTS)
    result.update({key: supplied[key] for key in SHARED_FIELDS if key in supplied})
    local = {key: value for key, value in (overrides or {}).items() if key in SHARED_FIELDS}
    result.update(deepcopy(local))
    def path_base(key):
        if key in local:
            return Path(override_base or tool_root).resolve()
        return path.parent if key in supplied else Path(tool_root).resolve().parent
    if type(result['java_version']) is not int or result['java_version'] < 17:
        raise ValueError('Common java_version must be an integer of at least 17')
    for key in ('java_scan_inactivity_timeout_seconds', 'model_timeout_seconds', 'max_model_attempts'):
        if type(result[key]) is not int or result[key] <= 0:
            raise ValueError('Common ' + key + ' must be a positive integer')
    for key in ('model_provider', 'model_name', 'model_base_url', 'model_api_key_environment'):
        if not isinstance(result[key], str):
            raise ValueError('Common ' + key + ' must be text')
    if result['model_provider'] not in {'gemini', 'litellm', 'mock', 'openai_compatible', 'openai'}:
        raise ValueError('Unsupported common model_provider')
    for key in PATH_FIELDS:
        if result[key] is not None:
            if not isinstance(result[key], str) or not result[key].strip():
                raise ValueError('Common ' + key + ' must be a nonempty path or null')
            result[key] = str((path_base(key) / Path(result[key]).expanduser()).resolve())
    for key in ('classpath_jars', 'framework_jars'):
        values = result[key]
        if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
            raise ValueError('Common ' + key + ' must list paths')
        result[key] = [str((path_base(key) / Path(item).expanduser()).resolve()) for item in values]
    for key in ('eclipse_classpath_variables', 'eclipse_classpath_containers', 'eclipse_project_classpath_containers'):
        if not isinstance(result[key], dict):
            raise ValueError('Common ' + key + ' must be an object')
    variables = result['eclipse_classpath_variables']
    if not all(isinstance(value, str) and value.strip() for value in variables.values()):
        raise ValueError('Common eclipse_classpath_variables must map names to paths')
    result['eclipse_classpath_variables'] = {key: str((path_base('eclipse_classpath_variables') / Path(value).expanduser()).resolve())
                                           for key, value in variables.items()}
    projects = result['eclipse_project_classpath_containers']
    for field, bindings in [('eclipse_classpath_containers', result['eclipse_classpath_containers']),
                            *(('eclipse_project_classpath_containers', bindings) for bindings in projects.values())]:
        if not isinstance(bindings, dict):
            raise ValueError('Common Eclipse container bindings must be objects')
        for key, values in bindings.items():
            if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError('Common Eclipse containers must list paths')
            bindings[key] = [str((path_base(field) / Path(value).expanduser()).resolve()) for value in values]
    result['_common_config_path'] = str(path)
    return result
