"""Bind deployment to exact validated service, container and chart package bytes."""
import hashlib
import json
from pathlib import Path


def write_package_receipt(project):
    project=Path(project)
    paths=[project/'pom.xml',project/'Dockerfile',project/'.dockerignore',
        *project.joinpath('src').rglob('*'),*project.joinpath('helm').rglob('*'),*project.joinpath('target').glob('*.jar'),
        project/'image-variants.json',*project.joinpath('images').rglob('*'),*project.joinpath('external-jdbc').rglob('*')]
    files={p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in paths if p.is_file() and 'schema-cache' not in p.parts}
    path=project/'microservice-package.json'
    path.write_text(json.dumps(dict(schema_version='native-service-package-v1',files=files),indent=2)+'\n',encoding='utf-8')
    return path


def verify_package(project):
    project=Path(project).resolve();receipt=json.loads((project/'microservice-package.json').read_text())
    if receipt.get('schema_version')!='native-service-package-v1':raise ValueError('Unsupported package receipt')
    for relative,expected in receipt['files'].items():
        path=(project/relative).resolve()
        if not path.is_relative_to(project) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Validated service package changed: '+relative)
    return receipt
