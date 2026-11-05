"""Driver replacement verifies actual class ownership and keeps vendor API dependencies visible."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from zipfile import ZipFile
from xml.etree import ElementTree
import pytest
from models.jdbc_image_variant import JdbcDriverArtifact
from runtime.fixture_jdbc_tools.releases import file_hash
from runtime.service_deployment.driver_artifacts import audit_application,verified_driver
from runtime.service_generation.project_output import configure_executable_build
from runtime.service_generation.external_jdbc import prepare_external_driver
from test_microservice_packaging import specification


@pytest.fixture
def driver(tmp_path):
    src=tmp_path/'example';src.mkdir()
    (src/'Driver.java').write_text('package example; public class Driver { }')
    (src/'Consumer.java').write_text('package example; public class Consumer { public Driver value; }')
    result=subprocess.run(['javac','-d',str(tmp_path/'classes'),*map(str,src.glob('*.java'))],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    jar=tmp_path/'verified-driver.jar'
    with ZipFile(jar,'w') as archive:
        archive.writestr('example/Driver.class',(tmp_path/'classes/example/Driver.class').read_bytes())
        archive.writestr('META-INF/maven/example/driver/pom.properties','groupId=example\nartifactId=driver\nversion=1.0.0\n')
    return jar


def test_driver_hash_class_and_compiled_vendor_references(driver,tmp_path):
    artifact=JdbcDriverArtifact(path=driver.name,sha256=file_hash(driver),driverClass='example.Driver')
    assert verified_driver(artifact,tmp_path,'example.Driver')==driver
    jar=tmp_path/'application.jar'
    with ZipFile(jar,'w') as application:
        application.writestr('BOOT-INF/classes/example/Consumer.class',(tmp_path/'classes/example/Consumer.class').read_bytes())
    with pytest.raises(ValueError,match='directly references'):audit_application(jar,driver)
    artifact.sha256='0'*64
    with pytest.raises(ValueError,match='changed'):verified_driver(artifact,tmp_path,'example.Driver')


def test_nested_driver_is_not_silently_shadowed(driver,tmp_path):
    jar=tmp_path/'application.jar'
    with ZipFile(jar,'w') as application:application.writestr('BOOT-INF/lib/driver.jar',driver.read_bytes())
    with pytest.raises(ValueError,match='shadows'):audit_application(jar,driver)


def test_production_catalogue_is_rejected(tmp_path):
    jar=tmp_path/'application.jar'
    with ZipFile(jar,'w') as application:
        application.writestr('BOOT-INF/classes/data.json','{"schema_version":"fixture-jdbc-catalogue-v1"}')
    with pytest.raises(ValueError,match='catalogue or dataset'):audit_application(jar,production=True)


def test_managed_packaging_externalizes_exact_maven_owner_without_touching_native_pom(driver,tmp_path):
    native=tmp_path/'native-pom.xml';native.write_text('<project><modelVersion>4.0.0</modelVersion></project>')
    original=native.read_bytes();project=tmp_path/'wrapper';project.mkdir()
    pom=project/'pom.xml';pom.write_bytes(original)
    class Verifier:
        def _arguments(self):return ['verified-maven']
        def _run(self,arguments,directory):
            output=next(arg.partition('=')[2] for arg in arguments if arg.startswith('-Dmdep.outputFile='))
            Path(output).write_text(str(driver),encoding='utf-8')
            return subprocess.CompletedProcess(arguments,0,'','')
    context=SimpleNamespace(pom_path=str(pom),verifier=Verifier())
    spec=specification();spec.databases['default'].driverClass='example.Driver'
    path=prepare_external_driver(context,spec,tmp_path)
    assert file_hash(path)==file_hash(driver) and path.parent.parent==project/'external-jdbc'
    configure_executable_build(context,external_driver=path)
    first=pom.read_bytes();configure_executable_build(context,external_driver=path)
    assert pom.read_bytes()==first
    root=ElementTree.parse(pom).getroot()
    assert root.findtext('.//configuration/layout')=='ZIP'
    assert root.findtext('.//configuration/excludes/exclude/groupId')=='example'
    assert root.findtext('.//configuration/excludes/exclude/artifactId')=='driver'
    assert native.read_bytes()==original


def test_namespaced_maven_pom_preserves_project_root_and_comments(tmp_path):
    pom=tmp_path/'pom.xml'
    pom.write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><!-- retained -->'
                   '<modelVersion>4.0.0</modelVersion></project>')
    configure_executable_build(SimpleNamespace(pom_path=str(pom)))
    assert '<project xmlns=' in pom.read_text() and '<!-- retained -->' in pom.read_text()
    assert 'ns0:project' not in pom.read_text()
