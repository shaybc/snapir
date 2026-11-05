"""Deployment never executes against modified or unvalidated package inputs."""
from pathlib import Path
import pytest
from runtime.service_deployment.receipt import write_package_receipt,verify_package
from runtime.service_deployment.runner import execute_deployment
from test_microservice_packaging import specification


def package(tmp_path):
    (tmp_path/'src/main/java').mkdir(parents=True)
    (tmp_path/'src/main/java/Operation.java').write_text('immutable')
    (tmp_path/'helm/chart').mkdir(parents=True)
    (tmp_path/'helm/chart/values.yaml').write_text('replicaCount: 1')
    (tmp_path/'target').mkdir();(tmp_path/'target/service.jar').write_bytes(b'fixture')
    for name in ['pom.xml','Dockerfile','.dockerignore']:(tmp_path/name).write_text(name)
    write_package_receipt(tmp_path)
    return tmp_path


def test_no_deployment_action_runs_by_default(tmp_path,monkeypatch):
    project=package(tmp_path)
    monkeypatch.setattr('subprocess.run',lambda *a,**k:pytest.fail('No external action was authorized'))
    result=execute_deployment(project,specification())
    assert result['commands']==[] and not result['deployed'] and not result['image_published']


def test_changed_jar_and_sources_are_rejected(tmp_path):
    project=package(tmp_path)
    (project/'target/service.jar').write_bytes(b'changed')
    with pytest.raises(ValueError,match='package changed'):verify_package(project)


def test_missing_deployment_values_prevent_cluster_access(tmp_path,monkeypatch):
    project=package(tmp_path)
    monkeypatch.setattr('subprocess.run',lambda *a,**k:pytest.fail('Cluster must not be contacted'))
    with pytest.raises(ValueError,match='incomplete'):execute_deployment(project,specification(),deploy=True)


def test_image_build_uses_updated_definition_without_changing_package(tmp_path,monkeypatch):
    import subprocess
    project=package(tmp_path)
    from zipfile import ZipFile
    with ZipFile(project/'target/service.jar','w') as application:
        application.writestr('data.txt',b'validated application')
        application.writestr('org/springframework/boot/loader/launch/PropertiesLauncher.class',b'inventory fixture')
        application.writestr('META-INF/MANIFEST.MF','Start-Class: example.Application\n')
    write_package_receipt(project)
    spec=specification()
    spec.deployment.image.repository='example.invalid/operation'
    spec.deployment.image.baseImage='eclipse-temurin@sha256:'+'a'*64
    validated=(project/'microservice-package.json').read_bytes()
    calls=[]
    monkeypatch.setattr('tools.deployment_tools.helm_validation.validate_helm',lambda *a,**k: {'helm_passed':True})
    monkeypatch.setattr('subprocess.run',lambda arguments,**kwargs: (
        calls.append(arguments) or subprocess.CompletedProcess(arguments,0,'sha256:'+'b'*64,'') ))
    result=execute_deployment(project,spec,build=True)
    staged=Path(result['staged_project'])
    receipt=__import__('json').loads((project/'image-build.json').read_text())
    assert receipt['tag'].startswith('example.invalid/operation:candidate-production-')
    assert calls==[['docker','build','--tag',receipt['tag'],result['image_context']],
        ['docker','image','inspect',receipt['tag'],'--format','{{.Id}}']]
    assert 'FROM '+spec.deployment.image.baseImage in (staged/'Dockerfile').read_text()
    assert (staged/'target/service.jar').read_bytes()==(project/'target/service.jar').read_bytes()
    from runtime.service_generation.deployment_configuration import read_deployment
    assert read_deployment(staged/'values.yaml')==spec
    assert not (staged/'microservice-deployment.json').exists()
    assert (project/'Dockerfile').read_text()=='Dockerfile'
    assert (project/'microservice-package.json').read_bytes()==validated
    verify_package(project)


def test_publish_requires_a_build_of_the_validated_jar(tmp_path,monkeypatch):
    project=package(tmp_path);spec=specification()
    spec.deployment.image.repository='example.invalid/operation'
    monkeypatch.setattr('subprocess.run',lambda *a,**k:pytest.fail('No owned image was built'))
    with pytest.raises(ValueError,match='before publishing'):
        execute_deployment(project,spec,publish=True)


def test_driver_check_reads_packaged_runtime_without_execution(tmp_path):
    from io import BytesIO
    from zipfile import ZipFile
    from runtime.service_deployment.jdbc_driver import driver_available
    spec=specification();spec.databases['default'].driverClass='example.Driver'
    (tmp_path/'target').mkdir()
    nested=BytesIO()
    with ZipFile(nested,'w') as library:library.writestr('example/Driver.class',b'fixture')
    with ZipFile(tmp_path/'target/service.jar','w') as application:
        application.writestr('BOOT-INF/lib/test-driver.jar',nested.getvalue())
    assert driver_available(tmp_path,spec)
    spec.databases['default'].driverClass='example.OtherDriver'
    assert not driver_available(tmp_path,spec)
