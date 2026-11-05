"""Render maintained Helm/container assets from typed, non-secret deployment inputs."""
import json
import shutil
from pathlib import Path
from runtime.operation_layout import application_project, service_record, service_artifacts
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
        if legacy_values.resolve()==values_path.resolve() and application_project(project)==project:
            raise ValueError('Editable values.yaml must live outside the generated chart directory')
        if legacy_values.resolve()!=values_path.resolve():legacy_values.unlink()
    schema = dict(type='object',required=['operation','image','service','databases'],properties={
        'replicaCount':dict(type='integer',minimum=1),
        'operation':dict(type='object',required=['identity','database','initialization']),
        'service':dict(type='object',required=['port'],properties={'port':dict(type='integer',minimum=1024,maximum=65535)}),
        'image':dict(type='object',required=['repository','digest']), 'databases':dict(type='object')})
    (chart/'values.schema.json').write_text(json.dumps(schema,indent=2)+'\n',encoding='utf-8')
    jars = [p for p in (application_project(project)/'target').glob('*.jar') if not p.name.endswith('.original')]
    if len(jars)!=1: raise ValueError('Expected exactly one packaged executable service JAR')
    environment=Environment(undefined=StrictUndefined,variable_start_string='[[',variable_end_string=']]')
    from runtime.service_deployment.driver_artifacts import selected_driver
    external_driver=selected_driver(project,spec,values_path.parent)
    if external_driver and application_project(project)!=project:
        (project/'jdbc').mkdir(exist_ok=True)
        if external_driver.resolve()!=(project/'jdbc/jdbc-driver.jar').resolve():shutil.copyfile(external_driver,project/'jdbc/jdbc-driver.jar')
    docker=environment.from_string((templates/'microservice/Dockerfile.j2').read_text()).render(
        base_image=deployment.image.baseImage,jar_name=jars[0].name,jar_source=jars[0].relative_to(project).as_posix(),port=spec.http.port,
        external_driver=bool(external_driver))
    (project/'Dockerfile').write_text(docker+'\n',encoding='utf-8')
    shutil.copyfile(templates/'microservice/dockerignore',project/'.dockerignore')
    if application_project(project)!=project:
        (project/'.dockerignore').write_text('*\n!application/\napplication/*\n!application/target/\napplication/target/*\n!application/target/*.jar\n!jdbc/\n!jdbc/jdbc-driver.jar\n',encoding='utf-8')
    service_artifacts(project).mkdir(parents=True,exist_ok=True)
    readiness=deployment_readiness(spec)
    service_record(project,'deployment-readiness.json').write_text(json.dumps(readiness,indent=2)+'\n',encoding='utf-8')
    return chart, readiness
