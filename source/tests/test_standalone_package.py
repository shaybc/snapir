"""Packaged projects retain the original Maven build and launch workflow after relocation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
import yaml

from runtime.behavior_conversion.standalone_runner import write_standalone_runner
from runtime.behavior_conversion.standalone_packaging import write_standalone_packaging
from runtime.fixture_demo.preparation import prepare_operation_demo
from runtime.fixture_jdbc_tools.releases import file_hash
from runtime.fixture_jdbc_tools.releases import verify_directory
from runtime.service_generation.deployment_configuration import read_deployment
from runtime.service_deployment.driver_artifacts import verified_driver
from test_fixture_demo import operation,free_port
from test_standalone_runner import DRIVER


pytestmark=pytest.mark.skipif(os.name!='nt',reason='Generated distribution launchers are Windows batch files')


def command(args,**kwargs):
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,**kwargs)
    assert result.returncode==0,result.stderr+result.stdout
    return result


@pytest.mark.parametrize('sibling_layout',[False,True])
def test_package_retains_identical_maven_project_for_production_and_demo(tmp_path,sibling_layout):
    root,project,assets=operation(tmp_path/'original location')
    repository=project
    if sibling_layout:
        holding=project.with_name('temporary-native');project.rename(holding);project.mkdir()
        holding.rename(project/'standalone');project=project/'standalone'
        assets=next((project/'src/test/resources/shared-test-assets').rglob('manifest.json')).parent
        write_standalone_runner(project,root,SimpleNamespace(service_api=SimpleNamespace(type_name='Example')))
        binding=project/'standalone/operation.json';data=json.loads(binding.read_text())
        data['runtime_config']=os.path.relpath(root/'runtime-config.json',binding.parent).replace('\\','/')
        binding.write_text(json.dumps(data))
        service=repository/'microservice'
        for name in ['application','integration-runtime','test-support']:
            source=service/name/'src/main/resources/images/kept.txt';source.parent.mkdir(parents=True)
            source.write_text('source resource preserved')
            (service/name/'pom.xml').write_text('<project/>')
            cache=service/name/'target/ignored.class';cache.parent.mkdir();cache.touch()
        (service/'pom.xml').write_text('<project/>')
        chart=service/'helm/example';chart.mkdir(parents=True)
        shutil.copyfile(project/'values.yaml',chart/'values.yaml')
    main=project/'src/main/java/Example.java';main.parent.mkdir(parents=True)
    main.write_text('''public class Example {
 public String execute(String xml,java.sql.Connection connection) throws Exception {
  if(connection.isClosed())throw new IllegalStateException();return xml;
 }
}''')
    pom=project/'pom.xml'
    pom.write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>test.portable</groupId><artifactId>Example</artifactId><version>1</version>
<properties><maven.compiler.release>25</maven.compiler.release></properties>
<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.14.1</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.5.4</version></plugin></plugins></build>
<dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId><artifactId>jackson-databind</artifactId><version>2.18.2</version></dependency>
<dependency><groupId>il.co.dcd</groupId><artifactId>behavior-verification</artifactId><version>1.0.0</version><scope>test</scope></dependency>
<dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.10.0</version><scope>test</scope></dependency></dependencies></project>''')
    tests=project/'src/test/java/ExampleTest.java';tests.parent.mkdir(parents=True,exist_ok=True)
    tests.write_text('public class ExampleTest { @org.junit.jupiter.api.Test void helperAvailable() throws Exception { org.junit.jupiter.api.Assertions.assertNotNull(Class.forName("il.co.dcd.verification.fixtures.FixtureStore")); } }')
    write_standalone_packaging(project)
    (project/'README.md').write_text('User project documentation')
    (project/'.mvn').mkdir();(project/'.mvn/maven.config').write_text('-Dproject.note=retained\n')
    nested=project/'standalone/test-support/behavior-verification/target';nested.mkdir()
    (nested/'ignored.class').write_text('old build output')
    config=root/'runtime-config.json'
    config.write_text(json.dumps(dict(databases=dict(default=dict(jdbc_url='jdbc:fixture:host:2345/schema',
        driver_class='FixtureDriver',user='test-user',password='test-password')))))
    driver=tmp_path/'driver';driver.mkdir();(driver/'FixtureDriver.java').write_text(DRIVER)
    command(['javac','-d',str(driver),str(driver/'FixtureDriver.java')])
    (project/'lib').mkdir()
    command(['jar','--create','--file',str(project/'lib/vendor-driver.jar'),'-C',str(driver),'FixtureDriver.class'])
    (project/'standalone/sample-request.xml').write_text('<Request><Id>7</Id></Request>')
    prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())
    assert prepared['status']=='prepared',prepared
    overlay=project/'demo-values.yaml';overlay_values=yaml.safe_load(overlay.read_text())
    catalogue=json.loads(Path(prepared['catalogue']).read_text())
    fixture_prefix=next(iter(next(iter(catalogue['scenarios'].values()))['resources'].values()))['fixtures'][0]['asset_root']
    overlay_values['demoInfrastructure']['assetRootMap']={fixture_prefix:'/fixtures/bank'}
    overlay.write_text(yaml.safe_dump(overlay_values,sort_keys=False))
    protected={path:file_hash(path) for path in [pom,main,config,project/'standalone/operation.json',project/'values.yaml',overlay,*assets.iterdir()]}
    environment=os.environ.copy();environment['MAVEN_ARGS']='--offline'
    build=command(['cmd','/d','/c','call',str(repository/'package-standalone-operation.bat')],cwd=tmp_path,env=environment)
    assert 'test-password' not in build.stdout+build.stderr
    package=repository/'Example.PKG'
    package_repository=package
    if sibling_layout:
        for name in ['application','integration-runtime','test-support']:
            assert (package/'microservice'/name/'src/main/resources/images/kept.txt').is_file()
            assert not (package/'microservice'/name/'target').exists()
        assert (package/'microservice/helm/example/values.yaml').is_file()
        assert (package/'package-standalone-operation.bat').is_file()
        package=package/'standalone';assert package.is_dir()
    assert all(file_hash(path)==value for path,value in protected.items())
    for name in ['pom.xml','.gitignore','values.yaml','run-operation.bat','run-operation-demo.bat',
                 'standalone/StandaloneLaunch.java','standalone/packaging/PackageMicroserviceValues.java']:
        assert (package/name).is_file()
    assert (package/'pom.xml').read_bytes()==pom.read_bytes()
    assert (package/'values.yaml').read_bytes()==(project/'values.yaml').read_bytes()
    assert {p.relative_to(project/'src'):p.read_bytes() for p in (project/'src').rglob('*') if p.is_file()}=={
        p.relative_to(package/'src'):p.read_bytes() for p in (package/'src').rglob('*') if p.is_file()}
    assert not any((package/name).exists() for name in ['target','.demo-scenario-generation','.demo-scenario-verification','operation-demo-scenarios.json','demo-preparation.json'])
    assert not any((package/name).exists() for name in ['lib/operation.jar','standalone/launcher.jar','package.json','build-and-run-operation.bat','standalone/test-support/behavior-verification/target'])
    assert (package/'lib/vendor-driver.jar').read_bytes()==(project/'lib/vendor-driver.jar').read_bytes()
    assert len(list((package/'lib').glob('*.jar')))==1
    assert (package/'README.md').read_bytes()==(project/'README.md').read_bytes()
    assert (package/'.mvn/maven.config').read_bytes()==(project/'.mvn/maven.config').read_bytes()
    for name in ['run-operation.bat','run-operation-demo.bat']:
        assert (package/name).read_bytes()==(project/name).read_bytes()
    assert (package_repository/'package-standalone-operation.bat').read_bytes()==(repository/'package-standalone-operation.bat').read_bytes()
    assert (package/'standalone/test-support/behavior-verification/pom.xml').is_file()
    assert (package/'standalone/test-support/behavior-verification/src/main/java/il/co/dcd/verification/fixtures/FixtureStore.java').is_file()
    snapshot={path:file_hash(path) for path in package.rglob('*') if path.is_file()}
    duplicate=subprocess.run(['cmd','/d','/c','call',str(repository/'package-standalone-operation.bat')],cwd=tmp_path,
        capture_output=True,text=True,timeout=45)
    assert duplicate.returncode!=0 and all(file_hash(path)==value for path,value in snapshot.items())
    relocated=tmp_path/'another machine with spaces'/'Example.PKG';relocated.parent.mkdir()
    shutil.copytree(package_repository,relocated)
    if sibling_layout:relocated=relocated/'standalone'
    # Make every original path unavailable; build exclusively from the copied project.
    root.rename(root.with_name('unavailable-original-tree'))
    env=environment;assert shutil.which('mvn',path=env['PATH']) is not None
    production=command(['cmd','/d','/c','call',str(relocated/'run-operation.bat'),'standalone/sample-request.xml'],cwd=tmp_path,env=env)
    assert production.stdout=='<Request><Id>7</Id></Request>'
    assert not (relocated/'standalone/.demo-runtime').exists()
    demo=command(['cmd','/d','/c','call',str(relocated/'run-operation-demo.bat')],cwd=tmp_path,env=env)
    assert demo.stdout=='<Request><Id>7</Id></Request>'
    report=json.loads((relocated/'standalone/.demo-runtime/last-run.json').read_text())
    assert report['status']=='completed' and not report['replay']['failed']
    assert json.loads((relocated/'standalone/.demo-runtime/server.json').read_text())['status']=='stopped'
    assert str(root) not in (relocated/'demo/catalogue.json').read_text()
    values=read_deployment(relocated/'values.yaml',overlays=[relocated/'demo-values.yaml'])
    infrastructure=values.demoInfrastructure
    verify_directory(relocated/infrastructure.toolRoot,infrastructure.bundleId,infrastructure.manifestHash)
    verified_driver(values.deployment.image.jdbcDriver,relocated,values.databases['demo'].driverClass)
    assert (relocated/infrastructure.catalogue).is_file()
    assert infrastructure.catalogueHash==json.loads((relocated/'standalone/operation.json').read_text())['demo']['catalogue_hash']
    copied_catalogue=json.loads((relocated/infrastructure.catalogue).read_text())
    prefix=next(iter(next(iter(copied_catalogue['scenarios'].values()))['resources'].values()))['fixtures'][0]['asset_root']
    assert infrastructure.assetRootMap=={prefix:'/fixtures/bank'}
    assert values.databases['demo'].credentialsSecret.model_dump()==overlay_values['databases']['demo']['credentialsSecret']
    command(['cmd','/d','/c','mvn','--batch-mode','-q','test'],cwd=relocated,env=environment)
    surefire=ElementTree.parse(relocated/'target/surefire-reports/TEST-ExampleTest.xml').getroot()
    assert surefire.get('tests')=='1' and surefire.get('failures')=='0' and surefire.get('errors')=='0'
    # A developer's source edit is compiled by the SAME run batch, never hidden behind an old JAR.
    copied=relocated/'src/main/java/Example.java'
    copied.write_text(copied.read_text().replace('return xml;', 'return "<Changed/>";'))
    changed=command(['cmd','/d','/c','call',str(relocated/'run-operation.bat'),'standalone/sample-request.xml'],cwd=tmp_path,env=environment)
    assert changed.stdout=='<Changed/>'


def test_generation_adds_packaging_files_and_preserves_user_gitignore(tmp_path):
    project=tmp_path/'generated/SME/Example';project.mkdir(parents=True)
    contract=SimpleNamespace(service_api=SimpleNamespace(type_name='Example'))
    write_standalone_runner(project,project.parent.parent,contract)
    assert (project/'package-standalone-operation.bat').is_file()
    assert (project/'standalone/packaging/pom.xml').is_file()
    ignore=project/'.gitignore';assert '/target/' in ignore.read_text() and '/*.PKG/' in ignore.read_text()
    ignore.write_text('# user-owned\ncustom/\n');before=ignore.read_bytes()
    write_standalone_runner(project,project.parent.parent,contract)
    assert ignore.read_bytes()==before


def test_generation_removes_only_obsolete_binary_packaging_templates(tmp_path):
    project=tmp_path/'Example';folder=project/'standalone/packaging';folder.mkdir(parents=True)
    for name in ['StandalonePackageBuild.java','build-and-run-operation.bat','run-operation.bat','README.md']:
        (folder/name).write_text('obsolete converter template')
    user=folder/'user-notes.txt';user.write_text('preserved')
    write_standalone_packaging(project)
    assert user.read_text()=='preserved'
    assert not (folder/'StandalonePackageBuild.java').exists()
    assert not (folder/'build-and-run-operation.bat').exists()
    assert (folder/'pom.xml').is_file()


def test_operation_gitignore_keeps_repo_assets_and_excludes_generated_output(tmp_path):
    project=tmp_path/'Example';project.mkdir()
    write_standalone_packaging(project)
    command(['git','init','--quiet',str(project)])
    excluded=['target/classes/Example.class','standalone/test-support/behavior-verification/target/tool.jar',
        'Example.PKG/pom.xml','standalone/.demo-runtime/server.json','runtime-config.json','execution.log']
    retained=['pom.xml','src/main/java/Example.java','src/test/resources/shared-test-assets/bank/fixtures.json',
        'values.yaml','demo-values.yaml','demo/tools/bundle/jdbc/fixture-jdbc-driver.jar',
        'demo/fixtures/bank/manifest.json','standalone/test-support/behavior-verification/src/main/java/Helper.java',
        'run-operation.bat','run-operation-demo.bat','package-standalone-operation.bat']
    for name in excluded+retained:
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
        status=subprocess.run(['git','check-ignore','--quiet','--no-index',name],cwd=project,timeout=15).returncode
        assert status==(0 if name in excluded else 1),name


def test_values_packaging_rebases_external_driver_and_rejects_duplicate_keys(tmp_path):
    project=tmp_path/'operation';project.mkdir()
    output=tmp_path/'package';output.mkdir()
    vendor=tmp_path/'external driver.jar'
    with ZipFile(vendor,'w') as jar:jar.writestr('vendor/Driver.class',b'driver-marker')
    values=dict(image=dict(jdbcDriver=dict(path='../external driver.jar',sha256=file_hash(vendor),driverClass='vendor.Driver')),
        operation=dict(identity='INTERNET/Example'),custom=dict(preserve='unchanged'))
    path=project/'values.yaml';path.write_text(yaml.safe_dump(values,sort_keys=False));before=path.read_bytes()
    templates=Path('source/templates/native_operations/standalone').resolve()
    repository=Path.home()/'.m2/repository'
    jars=[repository/'com/fasterxml/jackson/core'/name/'2.18.2'/(name+'-2.18.2.jar')
          for name in ('jackson-databind','jackson-core','jackson-annotations')]
    jars.append(repository/'org/yaml/snakeyaml/2.4/snakeyaml-2.4.jar')
    classpath=os.pathsep.join(map(str,jars));classes=tmp_path/'classes'
    probe=tmp_path/'ValuesProbe.java'
    probe.write_text('''import java.nio.file.*;
public class ValuesProbe { public static void main(String[] args) throws Exception {
 PackageMicroserviceValues.stage(Path.of(args[0]),Path.of(args[1]),DemoBinding.JSON.createObjectNode());
}}''')
    command(['javac','-cp',classpath,'-d',str(classes),str(probe),str(templates/'DemoBinding.java'),
        str(templates/'packaging/PackageFiles.java'),str(templates/'packaging/PackageMicroserviceValues.java')])
    args=['java','-cp',str(classes)+os.pathsep+classpath,'ValuesProbe',str(project),str(output)]
    command(args)
    copied=yaml.safe_load((output/'values.yaml').read_text())
    assert copied['image']['jdbcDriver']['path']=='lib/external driver.jar'
    assert copied['custom']==values['custom'] and path.read_bytes()==before
    assert (output/'lib/external driver.jar').read_bytes()==vendor.read_bytes()
    path.write_text('image: {}\nimage: {}\n')
    assert subprocess.run(args,capture_output=True,timeout=30).returncode!=0


def test_repository_copy_preserves_user_assets_and_module_source_resources(tmp_path):
    source=tmp_path/'operation';output=tmp_path/'copy';source.mkdir();output.mkdir()
    kept=['images/logo.txt','microservice/application/src/main/resources/target/business.txt',
        'microservice/integration-runtime/src/main/resources/images/diagram.txt']
    for name in kept+['target/stale.class','microservice/application/target/stale.class']:
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
    templates=Path('source/templates/native_operations/standalone').resolve()
    repo=Path.home()/'.m2/repository/com/fasterxml/jackson/core'
    cp=os.pathsep.join(str(repo/name/'2.18.2'/(name+'-2.18.2.jar')) for name in ['jackson-databind','jackson-core','jackson-annotations'])
    probe=tmp_path/'CopyProbe.java';probe.write_text('import java.nio.file.*; public class CopyProbe { public static void main(String[] args) throws Exception { PackageProjectFiles.stage(Path.of(args[0]),Path.of(args[1])); } }')
    classes=tmp_path/'classes'
    command(['javac','-cp',cp,'-d',str(classes),str(probe),str(templates/'DemoBinding.java'),str(templates/'packaging/PackageFiles.java'),str(templates/'packaging/PackageProjectFiles.java')])
    command(['java','-cp',str(classes)+os.pathsep+cp,'CopyProbe',str(source),str(output)])
    for name in kept:assert (output/name).read_bytes()==(source/name).read_bytes()
    assert not (output/'target').exists() and not (output/'microservice/application/target').exists()
