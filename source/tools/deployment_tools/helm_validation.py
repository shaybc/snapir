"""Execute Helm validation and inspect rendered references without contacting a cluster."""
import json
import subprocess
from pathlib import Path
from runtime.operation_layout import service_artifacts
import yaml


def validate_helm(chart, spec, executable='helm', kubernetes_version='1.34.0', *, values_path=None, overlays=()):
    """Require lint, template rendering, mount/selector references, and a packaged chart."""
    chart=Path(chart); commands=[]
    values_path=Path(values_path) if values_path is not None else chart.parent.parent/'values.yaml'
    from runtime.service_generation.deployment_configuration import read_deployment
    if read_deployment(values_path,overlays=overlays)!=spec:raise ValueError('Helm values do not match validated deployment settings')
    value_args=[argument for path in [values_path,*overlays] for argument in ('--values',str(path))]
    for arguments in ([executable,'lint',str(chart),'--strict',*value_args],
            [executable,'template',chart.name,str(chart),'--namespace',spec.deployment.namespace or 'validation',*value_args],
            [executable,'package',str(chart),'--destination',str(chart.parent)]):
        result=subprocess.run(arguments,capture_output=True,text=True,timeout=120)
        commands.append(dict(command=arguments,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        if result.returncode:
            raise ValueError('Helm validation failed: '+result.stderr[-2000:]+result.stdout[-2000:])
    artifacts=service_artifacts(chart.parent.parent);artifacts.mkdir(parents=True,exist_ok=True)
    documents=list(yaml.safe_load_all(commands[1]['stdout']))
    from tools.deployment_tools.kubernetes_schema import validate_kubernetes
    schema_result=validate_kubernetes(documents,(artifacts if artifacts!=chart.parent.parent else chart.parent)/'schema-cache',kubernetes_version)
    indexed={d['kind']:d for d in documents if d}
    for kind in ('Deployment','Service','ConfigMap','ServiceAccount'):
        if kind not in indexed: raise ValueError('Missing rendered resource: '+kind)
    deploy=indexed['Deployment']; service=indexed['Service']; config=indexed['ConfigMap']
    pod=deploy['spec']['template']; container=pod['spec']['containers'][0]
    if service['spec']['selector'] != deploy['spec']['selector']['matchLabels'] or not all(
            pod['metadata']['labels'].get(k)==v for k,v in service['spec']['selector'].items()):
        raise ValueError('Helm service selector does not match the application pod')
    if container['ports'][0]['containerPort'] != spec.http.port: raise ValueError('Helm HTTP port changed')
    if pod['spec']['volumes'][0]['configMap']['name'] != config['metadata']['name']:
        raise ValueError('Helm ConfigMap reference changed')
    if json.loads(config['data']['operation-initialization.json'])!=spec.operation.initialization:
        raise ValueError('Helm initialization values or original key casing changed')
    runtime=yaml.safe_load(config['data']['application.yaml'])['native-runtime']
    if runtime['operation']['database'] != (spec.operation.database or ''): raise ValueError('Helm database selection changed')
    from runtime.service_generation.helm_render_checks import validate_rendered_configuration
    validate_rendered_configuration(pod,container,runtime,spec)
    report=dict(helm_passed=True,values_file=str(values_path.resolve()),overlay_files=[str(Path(p).resolve()) for p in overlays],kubernetes_schema=schema_result,resource_kinds=sorted(indexed),commands=commands,
        chart_package=str(chart.parent/(chart.name+'-1.0.0.tgz')),deployed=False)
    ((artifacts if artifacts!=chart.parent.parent else chart.parent)/'helm-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
