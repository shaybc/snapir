"""Load converter-compatible configuration fields without importing migration configuration."""
import os
import codecs
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
import yaml

TOOL_ROOT = Path(__file__).resolve().parents[1]
PATH_FIELDS = ('source_root', 'output_root', 'approved_library_root', 'java_home',
               'maven_settings_path', 'maven_local_repository')
DEFAULTS = dict(source_encoding='UTF-8', java_version=25, java_home=None, java_scan_inactivity_timeout_seconds=900,
    classpath_jars=[], framework_jars=[], eclipse_classpath_variables={}, eclipse_classpath_containers={},
    eclipse_project_classpath_containers={}, maven_settings_path=None, maven_local_repository=None,
    model_provider='litellm', model_name='', model_base_url='', model_api_key_environment='AI_API_KEY',
    model_timeout_seconds=900, max_model_attempts=3, model_stream=False, output_root='./work', approved_library_root='./approved',
    native_package='com.company.nativeformats', request_character_limit=2000000, target_java_version=17,
    format_base_class='com.ibm.dse.base.FormatElement',
    decorator_base_classes=['com.ibm.dse.base.FormatDecorator', 'com.ibm.il.dse.cc.decorator.FormatDecoratorHolder'],
    source_excludes=['.git', '.venv', 'target', 'bin', 'build', 'node_modules'], known_dependencies=[])


def load_config(path):
    """Resolve paths relative to YAML; reject invalid tool settings, never persist credentials."""
    path = Path(path).resolve()
    supplied = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    if not isinstance(supplied, dict):
        raise ValueError('Configuration must be a YAML object')
    unknown = set(supplied) - set(DEFAULTS) - {'source_root'}
    if unknown:
        raise ValueError('Unsupported config fields; copy only documented sections: ' + ', '.join(sorted(unknown)))
    result = {**deepcopy(DEFAULTS), **supplied}
    try:
        if not isinstance(result['source_encoding'], str) or not result['source_encoding'].strip():
            raise ValueError('source_encoding must be a nonempty encoding name')
        codecs.lookup(result['source_encoding'])
    except LookupError as error:
        raise ValueError('Unsupported source_encoding: ' + result['source_encoding']) from error
    if not result.get('source_root'):
        raise ValueError('source_root is required')
    for key in PATH_FIELDS:
        if result.get(key):
            result[key] = str((path.parent / Path(result[key]).expanduser()).resolve())
    for key in ('classpath_jars', 'framework_jars'):
        if not isinstance(result[key], list):
            raise ValueError(key + ' must be a list')
        result[key] = [str((path.parent / item).resolve()) for item in result[key]]
    for key in ('eclipse_classpath_variables', 'eclipse_classpath_containers', 'eclipse_project_classpath_containers'):
        if not isinstance(result[key], dict):
            raise ValueError(key + ' must be an object')
    result['eclipse_classpath_variables'] = {k: str((path.parent / v).resolve())
        for k, v in result['eclipse_classpath_variables'].items()}
    for bindings in [result['eclipse_classpath_containers'], *result['eclipse_project_classpath_containers'].values()]:
        for key, values in bindings.items():
            bindings[key] = [str((path.parent / item).resolve()) for item in values]
    for key in ('model_timeout_seconds', 'java_scan_inactivity_timeout_seconds', 'max_model_attempts',
                'request_character_limit', 'target_java_version', 'java_version'):
        if not isinstance(result[key], int) or isinstance(result[key], bool) or result[key] <= 0:
            raise ValueError(key + ' must be a positive integer')
    if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', result['native_package'], re.ASCII):
        raise ValueError('native_package must be a Java package name')
    if result['model_provider'] not in {'litellm', 'gemini'}:
        raise ValueError('model_provider must be litellm or gemini')
    if not isinstance(result['model_stream'], bool):
        raise ValueError('model_stream must be true or false')
    if result['java_version'] < 17 or result['target_java_version'] < 17:
        raise ValueError('The scanner and common API require Java 17 or later')
    result['_config_path'] = str(path)
    return result


def java_environment(config):
    """Resolve a matching JDK for scanner infrastructure only, never generated components."""
    environment = os.environ.copy()
    home = config.get('java_home') or os.environ.get('JAVA_HOME')
    if home:
        environment['JAVA_HOME'] = str(home)
        environment['PATH'] = str(Path(home) / 'bin') + os.pathsep + environment.get('PATH', '')
    java = shutil.which('java', path=environment.get('PATH'))
    if not java:
        raise ValueError('Java not found; set java_home in config.yaml')
    result = subprocess.run([java, '-version'], env=environment, capture_output=True, text=True, timeout=10)
    version = re.search(r'version\s+"(\d+)', result.stderr + result.stdout)
    if result.returncode or not version or int(version[1]) != config['java_version']:
        raise ValueError('Selected JDK does not match java_version=' + str(config['java_version']))
    return java, environment
