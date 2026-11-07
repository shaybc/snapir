"""Resolve service URLs by execution profile without coupling addresses to API versions."""
from urllib.parse import urlsplit, urlunsplit

from models.service_address import ServiceAddress
from models.service_environment import ServiceEnvironment
from runtime.service_generation.deployment_configuration import service_name


def operation_address(profile, channel, operation, property_name, *, saved=None):
    """Combine explicit target overrides with environment conventions and legacy address fields."""
    environment = profile.deployment_environment
    settings = profile.service_environments.get(environment) if hasattr(profile, 'service_environments') else None
    values = profile.deployment_values.get(channel + '/' + operation, {})
    data = saved.model_dump(mode='json', exclude_none=True) if saved else {}
    name = values.get('service_name') or data.get('service_name') or service_name(channel, operation)
    namespace = values.get('namespace', settings.namespace if settings else data.get('namespace', ''))
    port = values.get('service_port', values.get('container_port', data.get('port') or
                     (settings.service_port if settings else profile.deployment_defaults.container_port)))
    override = settings is not None or any(field in values for field in ('service_name','namespace','service_port','container_port'))
    internal = values.get('internal_base_url') or (None if override else data.get('internal_base_url'))
    if not internal:
        host = name + ('.' + namespace + '.svc.' + settings.cluster_domain if namespace and settings else
                       '.' + namespace + '.svc' if namespace else '')
        internal = 'http://' + host + ':' + str(port)
    external = values.get('external_base_url') or values.get('base_url')
    if not external and settings and settings.external_url_pattern:
        external = settings.external_url_pattern.format(service_name=name, namespace=namespace, channel=channel, operation=operation)
    external = external or data.get('external_base_url') or data.get('base_url')
    if not external and getattr(profile, 'test_deployment', None):
        test = profile.test_deployment
        pattern = test.service_route_pattern.replace('${ms_name}', name).replace('{service_name}', name)
        if test.service_base_url:
            external = test.service_base_url.rstrip('/') + '/' + pattern.lstrip('/')
            if test.service_external_port:
                parts = urlsplit(external)
                external = urlunsplit((parts.scheme, parts.hostname + ':' + str(test.service_external_port), parts.path, parts.query, parts.fragment))
    data.update(base_url_property=property_name, service_name=name, port=port, internal_base_url=internal)
    if namespace:
        data['namespace'] = namespace
    if external:
        data['external_base_url'] = external
    return ServiceAddress.model_validate(data)


def published_operation_address(profile, channel, operation, property_name, project, *, deployment=None):
    """Advertise the Service name/port from the approved descriptor, not an assumed container default."""
    from pathlib import Path
    definition = Path(project) / 'values.yaml'
    if deployment is None and not definition.is_file():
        return operation_address(profile, channel, operation, property_name)
    from runtime.service_generation.deployment_configuration import read_deployment
    spec = deployment or read_deployment(definition)
    key = channel + '/' + operation
    if spec.operation.identity != key:
        raise ValueError('Published deployment settings belong to another operation')
    values = dict(profile.deployment_values.get(key, {}), service_port=spec.http.port)
    if spec.http.serviceName:
        values['service_name'] = spec.http.serviceName
    if spec.deployment.namespace:
        values['namespace'] = spec.deployment.namespace
    settings = profile.model_copy(update={'deployment_values': dict(profile.deployment_values, **{key: values})})
    return operation_address(settings, channel, operation, property_name)


def service_url(address, execution):
    """Never silently route an in-cluster caller through an external Route."""
    if execution == 'microservice':
        value = address.internal_base_url
    elif execution == 'standalone':
        value = address.external_base_url or address.base_url
    else:
        raise ValueError('Unknown service execution profile')
    if value is None:
        raise ValueError('Missing ' + execution + ' service base URL for ' + str(address.base_url_property))
    return str(value).rstrip('/')


def client_properties(conn, config, profile, execution):
    """Project pinned API uses into runtime settings, applying current environment overrides."""
    from tools.state_store_tools.service_api_uses import list_service_uses
    result = {}
    for use in list_service_uses(conn, config.run_id):
        contract = use.contract
        from tools.operation_call_tools.published_calls import call_contract
        property_name = call_contract(use)['base_url_property']
        address = operation_address(profile, contract.channel, contract.operation_id,
                                    property_name, saved=use.address)
        result[address.base_url_property] = service_url(address, execution)
    return result
