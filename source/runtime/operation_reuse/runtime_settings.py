"""Prepare standalone service properties and portable component dependencies."""
import json
from pathlib import Path


def prepare_operation_reuse(conn, config, profile, project):
    """Preserve user runtime values while supplying known external service addresses."""
    from runtime.component_conversion.shared_dependencies import materialize_operation_dependencies
    from runtime.behavior_conversion.runtime_config import ensure_runtime_config
    from runtime.service_addresses import client_properties
    materialize_operation_dependencies(conn, config, profile, project)
    values = client_properties(conn, config, profile, 'standalone')
    if not values:
        return
    path = ensure_runtime_config(config.output_root)
    data = json.loads(path.read_text(encoding='utf-8'))
    urls = data.setdefault('service_urls', {})
    for property_name, url in values.items():
        urls.setdefault(property_name, url)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def configure_microservice_calls(conn, config, profile, spec, path):
    """Render internal endpoints into editable Helm values without changing business source."""
    from runtime.service_addresses import client_properties
    from runtime.service_generation.deployment_configuration import write_deployment
    values = client_properties(conn, config, profile, 'microservice')
    if not values:
        return spec
    merged = dict(values, **spec.serviceUrls)
    updated = spec.model_copy(update={'serviceUrls': merged})
    if updated != spec:
        write_deployment(path, updated)
    return updated
