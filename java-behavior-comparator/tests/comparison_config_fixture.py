"""Write independent tool settings that select a common converter YAML fixture."""
import yaml
from comparator.common_configuration import SHARED_FIELDS


def write_config(path, values):
    common = path.with_name(path.stem + '-common.yaml')
    common.write_text(yaml.safe_dump({key: value for key, value in values.items() if key in SHARED_FIELDS}), encoding='utf-8')
    local = {key: value for key, value in values.items() if key not in SHARED_FIELDS}
    path.write_text(yaml.safe_dump(dict(local, common_config_path=common.name)), encoding='utf-8')
