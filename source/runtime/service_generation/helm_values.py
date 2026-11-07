"""Translate the single editable Helm values document to the typed runtime configuration."""
from models.microservice_deployment import MicroserviceDeployment


def deployment_values(spec):
    """Return Helm-compatible settings, including the converter's build and namespace inputs."""
    d=spec.deployment
    operation=spec.operation.model_dump(mode='json')
    operation['database']=spec.operation.database or ''
    result = dict(schemaVersion=spec.schemaVersion,replicaCount=d.replicas,
        image=d.image.model_dump(mode='json',exclude_none=True),service=dict(port=spec.http.port),
        http=dict(path=spec.http.path),operation=operation,
        databases={k:v.model_dump(mode='json') for k,v in spec.databases.items()},
        resources=dict(requests=dict(cpu=d.cpuRequest,memory=d.memoryRequest),
                       limits=dict(cpu=d.cpuLimit,memory=d.memoryLimit)),
        deployment=dict(namespace=d.namespace),transactionPolicy=spec.transactionPolicy)
    if spec.demoInfrastructure is not None:
        result['demoInfrastructure']=spec.demoInfrastructure.model_dump(mode='json')
    if spec.http.serviceName:
        result['service']['name'] = spec.http.serviceName
    if spec.serviceUrls:
        result['serviceUrls'] = spec.serviceUrls
    return result


def deployment_from_values(values):
    """Validate every supported value; do not discard unknown configuration keys."""
    def keys(data,allowed):
        if not isinstance(data,dict):raise ValueError('Helm values must contain mappings')
        if any(not isinstance(key,str) for key in data):raise ValueError('Helm values keys must be strings')
        unknown=set(data)-set(allowed)
        if unknown:raise ValueError('Unsupported Helm values keys: '+', '.join(sorted(unknown)))
    keys(values,('schemaVersion','replicaCount','image','service','http','operation','databases','resources','deployment','transactionPolicy','demoInfrastructure','serviceUrls'))
    service=values.get('service',{});http=values.get('http',{});deployment=values.get('deployment',{})
    keys(service,('port','name'));keys(http,('path',));keys(deployment,('namespace',))
    resources=values.get('resources',{});keys(resources,('requests','limits'))
    requests=resources.get('requests',{});limits=resources.get('limits',{})
    keys(requests,('cpu','memory'));keys(limits,('cpu','memory'))
    if not isinstance(values.get('operation',{}),dict):raise ValueError('Helm operation values must be a mapping')
    operation=dict(values.get('operation',{}))
    if operation.get('database')=='':operation['database']=None
    return MicroserviceDeployment.model_validate(dict(
        schemaVersion=values.get('schemaVersion','native-microservice-v1'),operation=operation,
        http=dict(path=http.get('path'),port=service.get('port',8080),serviceName=service.get('name','')),databases=values.get('databases',{}),
        serviceUrls=values.get('serviceUrls',{}),
        transactionPolicy=values.get('transactionPolicy','preserve-source'),
        demoInfrastructure=values.get('demoInfrastructure'),
        deployment=dict(namespace=deployment.get('namespace',''),replicas=values.get('replicaCount',1),
            image=values.get('image',{}),cpuRequest=requests.get('cpu','250m'),cpuLimit=limits.get('cpu','1'),
            memoryRequest=requests.get('memory','256Mi'),memoryLimit=limits.get('memory','1Gi'))))
