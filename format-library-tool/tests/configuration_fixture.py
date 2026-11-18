"""Write separate common and tool YAML files for isolated format-tool regressions."""
import yaml
from format_library.common_configuration import SHARED_FIELDS


def write_config(path, values):
    shared = {key: value for key, value in values.items() if key in SHARED_FIELDS}
    local = {key: value for key, value in values.items() if key not in SHARED_FIELDS}
    if 'target_java_version' in local:
        shared['java_version'] = local.pop('target_java_version')
    common = path.with_name(path.stem + '-common.yaml')
    common.write_text(yaml.safe_dump(shared), encoding='utf-8')
    path.write_text(yaml.safe_dump(dict(local, common_config_path=common.name)), encoding='utf-8')
