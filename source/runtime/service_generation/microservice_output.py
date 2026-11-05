"""Attach maintained runtime/configuration and validate the generated wrapper package."""
import json
from pathlib import Path


def managed_resources(spec):
    """Return non-secret Spring defaults; Helm supplies production values on deployment."""
    properties = '\n'.join([
        'spring.config.import=optional:file:/etc/native-runtime/application.yaml',
        'native-runtime.operation.identity=' + spec.operation.identity,
        'native-runtime.operation.database=' + (spec.operation.database or ''),
        'native-runtime.initialization-file=classpath:operation-initialization.json',
        'native-operation.http.path=' + spec.http.path,
        'server.port=' + str(spec.http.port),
        'server.shutdown=graceful', 'spring.lifecycle.timeout-per-shutdown-phase=30s',
        'management.endpoints.web.exposure.include=health,info',
        'management.endpoint.health.probes.enabled=true',
        'management.endpoint.health.show-details=never',
        'management.endpoint.health.group.readiness.include=readinessState',
    ]) + '\n'
    return {'src/main/resources/application.properties':properties,
            'src/main/resources/operation-initialization.json':json.dumps(spec.operation.initialization,ensure_ascii=False)+'\n'}


def merge_managed_resources(output, resources):
    """Models cannot override the selected operation/configuration and managed probe settings."""
    files = dict(output['files'])
    for name, content in resources.items():
        if name in files and files[name] != content:
            raise ValueError('Wrapper must preserve converter-owned resource: ' + name)
        files[name] = content
    return dict(output,files=files)


def validate_initialization(files, spec):
    """External bindings describe consumed inputs; their use is verified by executable tests."""
    path = 'src/main/resources/initialization-bindings.json'
    if path not in files: raise ValueError('Wrapper must declare consumed initialization keys')
    bindings=json.loads(files[path])
    if set(bindings)!={'consumed_keys'} or not isinstance(bindings['consumed_keys'],list):
        raise ValueError('Invalid external initialization binding declaration')
    missing=set(spec.operation.initialization)-set(bindings['consumed_keys'])
    if missing: raise ValueError('Configured initialization keys have no native binding: '+str(sorted(missing)))


def package_microservice(project, spec, settings, *, values_path=None):
    """Package/validate charts separately from environment readiness or actual deployment."""
    from tools.deployment_tools.helm_renderer import render_helm
    from tools.deployment_tools.helm_validation import validate_helm
    result=dict(helm_passed=False,image_built=False,image_published=False,deployed=False)
    try:
        chart, readiness=render_helm(project,spec,values_path=values_path)
        if spec.operation.database and spec.databases[spec.operation.database].driverClass:
            from runtime.service_deployment.jdbc_driver import driver_available
            if not driver_available(project,spec,definition_root=Path(values_path).parent if values_path else project):
                readiness['deployment_ready']=False
                readiness['unresolved'].append('databases.'+spec.operation.database+'.driver runtime dependency')
                (Path(project)/'deployment-readiness.json').write_text(json.dumps(readiness,indent=2)+'\n',encoding='utf-8')
        result.update(readiness,chart=str(chart))
        result.update(validate_helm(chart,spec,settings.helm_executable,getattr(settings,'kubernetes_version','1.34.0'),values_path=values_path))
        from runtime.service_deployment.image_variants import prepare_image_variants
        result['image_variants']=prepare_image_variants(project,spec,values_path or Path(project)/'values.yaml')
        if not result['image_variants']['production'].get('context'):
            result['image_validation_failed']=True
            raise ValueError('Production image validation failed: '+result['image_variants']['production']['reason'])
        demo_values=Path(values_path or Path(project)/'values.yaml').parent/'demo-values.yaml'
        if result['image_variants'].get('demo',{}).get('context'):
            from runtime.service_generation.deployment_configuration import read_deployment
            demo=read_deployment(values_path or Path(project)/'values.yaml',overlays=[demo_values])
            result['demo_helm']=validate_helm(chart,demo,settings.helm_executable,
                getattr(settings,'kubernetes_version','1.34.0'),
                values_path=values_path or Path(project)/'values.yaml',overlays=[demo_values])
        elif demo_values.exists():
            from runtime.service_generation.deployment_configuration import read_deployment
            selected_demo=read_deployment(values_path or Path(project)/'values.yaml',overlays=[demo_values])
            if selected_demo.demoInfrastructure and selected_demo.demoInfrastructure.status=='prepared':
                result['image_validation_failed']=True
                raise ValueError('Prepared demo image validation failed: '+result['image_variants']['demo']['reason'])
    except Exception as error:
        result['helm_error']=str(error)
        if settings.require_helm_validation:
            result['packaging_passed']=False
            return result
    result['packaging_passed']=(result.get('helm_passed') or not settings.require_helm_validation) and not result.get('image_validation_failed')
    if result['packaging_passed']:
        from runtime.service_deployment.receipt import write_package_receipt
        result['package_receipt']=str(write_package_receipt(project))
    return result
