"""Resolve immutable operation identity and editable non-secret deployment settings."""
import json
import re
from pathlib import Path
import yaml
from models.microservice_deployment import MicroserviceDeployment


def service_name(channel, operation):
    """Produce a DNS label while preserving operation identity in application settings."""
    name = re.sub('[^a-z0-9-]', '-', (channel + '-' + operation).lower()).strip('-')
    if len(name) > 50:
        import hashlib
        name = name[:40] + '-' + hashlib.sha256(name.encode()).hexdigest()[:9]
    return name


def read_deployment(path, *, overlays=()):
    """Read a YAML deployment definition through the existing typed validation checks."""
    from runtime.service_generation.values_overlays import read_values
    return read_values([path,*overlays])[1]


def write_deployment(path, spec):
    """Write deployment settings as YAML while preserving their original names and value types."""
    from runtime.service_generation.helm_values import deployment_values
    Path(path).write_text(yaml.safe_dump(deployment_values(spec),sort_keys=False,allow_unicode=True),encoding='utf-8')


def load_deployment(item, *, persist=True, profile=None):
    """Seed once or preview without writes; never copy credentials or overwrite an edited definition."""
    project = Path(item['project'])
    path = project / 'values.yaml'
    identity = item['channel'] + '/' + item['operation_id']
    if path.exists():
        result = read_deployment(path)
    else:
        selected = 'default'
        standalone = project / 'standalone/operation.json'
        if standalone.exists():
            selected = json.loads(standalone.read_text(encoding='utf-8')).get('database', 'default')
        # Connection/resource requirements are supplied as accepted evidence, not inferred from Java text.
        contract = item['payload'].get('contract', {})
        signatures = contract.get('service_api', {}).get('method_signatures', [])
        jdbc_types={'Connection','java.sql.Connection','DataSource','javax.sql.DataSource'}
        jdbc = bool(any(resource.get('resource_type') in jdbc_types or resource.get('provider_type') in jdbc_types
                        for resource in contract.get('runtime_resources',[])) or
                    any(connection.get('resource_kind')=='jdbc' for connection in item['payload'].get('service_connections',[])) or
                    any('Connection ' in signature or 'DataSource ' in signature for signature in signatures))
        name = service_name(item['channel'], item['operation_id'])
        result = MicroserviceDeployment.model_validate(dict(
            operation=dict(identity=identity, database=selected if jdbc else None, initialization={}),
            http=dict(path=item['payload'].get('native_http_contract',{}).get('path','/api/' + identity),serviceName=name),
            databases={selected:dict(credentialsSecret=dict(name=name + '-database'))} if jdbc else {}))
        from runtime.behavior_conversion.verification_mode import test_based_mode
        if profile is not None and test_based_mode(profile):
            from runtime.service_addresses import operation_address
            address = operation_address(profile,item['channel'],item['operation_id'],'service.address')
            data = result.model_dump(mode='json')
            data['http'].update(port=address.port,serviceName=address.service_name)
            data['deployment']['namespace'] = address.namespace or ''
            result = MicroserviceDeployment.model_validate(data)
        if persist:
            write_deployment(path,result)
    if result.operation.identity != identity:
        raise ValueError('Deployment configuration belongs to another operation')
    connections = [record for record in item['payload'].get('service_connections', []) if record.get('configuration_contract')]
    template = project / 'connection-configuration.yaml'
    if persist and connections and not template.exists():
        # This is a deployment handoff, never values read from dseConnector.
        resources = [dict(channel=record['channel'], service=record['service_id'],
            parameters={parameter['name']: None for parameter in record['configuration_contract']['parameters']},
            parameterTypes={parameter['name']: parameter['type'] for parameter in record['configuration_contract']['parameters']},
            requirements=record.get('deployment_requirements', []),
            completeness=record['configuration_contract']['completeness']) for record in connections]
        template.write_text(yaml.safe_dump(dict(resources=resources), sort_keys=False, allow_unicode=True), encoding='utf-8')
    return result


def deployment_readiness(spec):
    """Report missing environment values separately from executable package validation."""
    missing = []
    if not spec.deployment.namespace: missing.append('deployment.namespace')
    if not spec.deployment.image.repository: missing.append('deployment.image.repository')
    if not spec.deployment.image.digest: missing.append('deployment.image.digest')
    if '@sha256:' not in spec.deployment.image.baseImage: missing.append('deployment.image.baseImage digest')
    if spec.operation.database:
        db = spec.databases[spec.operation.database]
        if not db.jdbcUrl: missing.append('databases.' + spec.operation.database + '.jdbcUrl')
        if not db.driverClass: missing.append('databases.' + spec.operation.database + '.driverClass')
    if spec.demoInfrastructure is not None:
        demo=spec.demoInfrastructure
        if demo.status!='prepared':missing.append('demoInfrastructure: saved operation fixtures unavailable')
        if not demo.enabled:missing.append('demoInfrastructure.enabled and read-only fixture mount')
        if not demo.repository or not demo.digest:missing.append('demoInfrastructure server image/digest')
    return dict(deployment_ready=not missing, unresolved=missing, deployed=False, image_published=False)
