"""Render maintained Helm/container assets from typed, non-secret deployment inputs."""
import json
import shutil
from pathlib import Path
import yaml
from jinja2 import Environment, StrictUndefined
from runtime.service_generation.deployment_configuration import service_name, deployment_readiness


def render_helm(project, spec, *, values_path=None, overlays=()):
    """Write a per-operation chart; user-owned deployment input remains authoritative."""
    project = Path(project)
    templates = Path(__file__).resolve().parents[2]/'templates'
    name = service_name(*spec.operation.identity.split('/', 1))
    chart = project/'helm'/name
    shutil.copytree(templates/'helm/native-operation', chart, dirs_exist_ok=True)
    chart_yaml = yaml.safe_load((chart/'Chart.yaml').read_text())
    chart_yaml['name'] = name
    (chart/'Chart.yaml').write_text(yaml.safe_dump(chart_yaml, sort_keys=False), encoding='utf-8')
    deployment = spec.deployment
    from runtime.service_generation.deployment_configuration import read_deployment,write_deployment
    values_path=Path(values_path) if values_path is not None else project/'values.yaml'
    if values_path.exists():
        if read_deployment(values_path,overlays=overlays)!=spec:raise ValueError('Helm values changed after configuration was loaded')
    else:write_deployment(values_path,spec)
    legacy_values=chart/'values.yaml'
    if legacy_values.exists():
        if legacy_values.resolve()==values_path.resolve():
            raise ValueError('Editable values.yaml must live outside the generated chart directory')
        legacy_values.unlink()
    schema = dict(type='object',required=['operation','image','service','databases'],properties={
        'replicaCount':dict(type='integer',minimum=1),
        'operation':dict(type='object',required=['identity','database','initialization']),
        'service':dict(type='object',required=['port'],properties={'port':dict(type='integer',minimum=1024,maximum=65535)}),
        'image':dict(type='object',required=['repository','digest']), 'databases':dict(type='object')})
    (chart/'values.schema.json').write_text(json.dumps(schema,indent=2)+'\n',encoding='utf-8')
    jars = [p for p in (project/'target').glob('*.jar') if not p.name.endswith('.original')]
    if len(jars)!=1: raise ValueError('Expected exactly one packaged executable service JAR')
    environment=Environment(undefined=StrictUndefined,variable_start_string='[[',variable_end_string=']]')
    from runtime.service_deployment.driver_artifacts import selected_driver
    external_driver=selected_driver(project,spec,values_path.parent)
    docker=environment.from_string((templates/'microservice/Dockerfile.j2').read_text()).render(
        base_image=deployment.image.baseImage,jar_name=jars[0].name,port=spec.http.port,
        external_driver=bool(external_driver))
    (project/'Dockerfile').write_text(docker+'\n',encoding='utf-8')
    shutil.copyfile(templates/'microservice/dockerignore',project/'.dockerignore')
    readiness=deployment_readiness(spec)
    (project/'deployment-readiness.json').write_text(json.dumps(readiness,indent=2)+'\n',encoding='utf-8')
    return chart, readiness
