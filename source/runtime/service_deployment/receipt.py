"""Bind deployment to exact validated service, container and chart package bytes."""
import hashlib
import json
from pathlib import Path
from runtime.operation_layout import application_project, service_artifacts, service_record


def write_package_receipt(project):
    project=Path(project)
    application=application_project(project)
    artifacts=service_artifacts(project);artifacts.mkdir(parents=True,exist_ok=True)
    paths=[project/'pom.xml',project/'Dockerfile',project/'.dockerignore',
        *project.joinpath('src').rglob('*'),
        *[p for module in ('application','integration-runtime','test-support') for p in [project/module/'pom.xml',*project.joinpath(module,'src').rglob('*')]],*project.joinpath('helm').rglob('*'),*application.joinpath('target').glob('*.jar'),
        project/'image-variants.json',*project.joinpath('images').rglob('*'),*project.joinpath('external-jdbc').rglob('*')]
    files={p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in paths if p.is_file() and 'schema-cache' not in p.parts}
    path=service_record(project,'microservice-package.json')
    extra={}
    if artifacts!=project:
        extra={p.relative_to(artifacts).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [artifacts/'image-variants.json',artifacts/'helm-validation.json',artifacts/'external-jdbc/driver.json',*artifacts.joinpath('images').rglob('*')]
            if p.is_file() and 'schema-cache' not in p.parts}
    path.write_text(json.dumps(dict(schema_version='native-service-package-v1',files=files,artifact_files=extra),indent=2)+'\n',encoding='utf-8')
    return path


def verify_package(project):
    project=Path(project).resolve();receipt=json.loads(service_record(project,'microservice-package.json').read_text())
    if receipt.get('schema_version')!='native-service-package-v1':raise ValueError('Unsupported package receipt')
    for relative,expected in receipt['files'].items():
        path=(project/relative).resolve()
        if not path.is_relative_to(project) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Validated service package changed: '+relative)
    artifacts=service_artifacts(project).resolve()
    for relative,expected in receipt.get('artifact_files',{}).items():
        path=(artifacts/relative).resolve()
        if not path.is_relative_to(artifacts) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Validated converter artifact changed: '+relative)
    return receipt
