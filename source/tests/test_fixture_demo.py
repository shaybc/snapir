"""Plan B uses installed tooling and saved references; generated business code stays oblivious."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from types import SimpleNamespace
from zipfile import ZipFile
import pytest
import yaml
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from runtime.test_assets.store import publish
from runtime.fixture_jdbc_tools.releases import digest,locate_release,file_hash
from runtime.fixture_demo.preparation import prepare_operation_demo,PINNED_BUNDLE
from runtime.fixture_demo.artifact_paths import demo_artifact,demo_workspace
from runtime.behavior_conversion.standalone_runner import write_standalone_runner
from runtime.service_generation.deployment_configuration import read_deployment,write_deployment
from runtime.service_deployment.image_variants import stage_image_variant,stage_server_image
from test_microservice_packaging import specification


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def operation(directory):
    root=directory/'generated';project=root/'INTERNET/Example';project.mkdir(parents=True)
    write_standalone_runner(project,root,SimpleNamespace(service_api=SimpleNamespace(type_name='Example')))
    write_deployment(project/'values.yaml',specification())
    bank=SharedFixtureBank(fixtures={
        'request':dict(kind='xml',value='<Request><Id>7</Id></Request>'),
        'database':dict(kind='database',value=dict(queries=[dict(sql='SELECT Value FROM T WHERE Id = ?',
            parameters=[7],columns=['Value'],rows=[['saved-value']],exception=None)]))})
    assets,manifest=publish(project/'src/test/resources/shared-test-assets','INTERNET/Example',{'purpose':'Plan B acceptance'},
        bank,JunitScenarioSuite(scenarios=[dict(scenario_id='definition',purpose='Saved data',
            native_entry=dict(owner_type='java.lang.String',method_name='isEmpty'),assertions=['definition'])]),ComparisonScenarioSuite())
    reference=lambda fixture:dict(asset_root=assets.relative_to(project).as_posix(),manifest_hash=digest(manifest.model_dump(mode='json')),
                                  fixture_id=fixture,pointer='')
    definition=dict(operation='INTERNET/Example',scenarios=[dict(scenario_id='success',input_xml=reference('request'),
        resources={'database':[reference('database')]})])
    definition_path=demo_artifact(project,'operation-demo-scenarios.json');definition_path.parent.mkdir(parents=True,exist_ok=True)
    definition_path.write_text(json.dumps(definition),encoding='utf-8')
    return root,project,assets


def test_unavailable_without_whole_operation_links_never_guesses(tmp_path):
    root,project,assets=operation(tmp_path)
    demo_artifact(project,'operation-demo-scenarios.json').unlink()
    before={p:file_hash(p) for p in assets.iterdir()}
    result=prepare_operation_demo(project,root,'INTERNET/Example')
    assert result['status']=='unavailable' and 'No saved whole-operation' in result['issues'][0]
    assert 'demo' not in json.loads((project/'standalone/operation.json').read_text())
    assert not (root/'demo-tools').exists()
    assert {p:file_hash(p) for p in assets.iterdir()}==before
    assert read_deployment(project/'values.yaml',overlays=[project/'demo-values.yaml']).demoInfrastructure.status=='unavailable'


def test_preparation_stages_only_pinned_tools_and_references(tmp_path):
    root,project,assets=operation(tmp_path)
    paths=[*assets.iterdir(),project/'values.yaml',root/'runtime-config.json']
    before={p:file_hash(p) for p in paths}
    report=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port())
    assert report['status']=='prepared',report
    assert {p:file_hash(p) for p in paths}==before
    catalogue=json.loads(Path(report['catalogue']).read_text())
    assert 'queries' not in json.dumps(catalogue) and 'saved-value' not in json.dumps(catalogue)
    assert not (project/'lib').exists() and not (project/'standalone/sample-request.json').exists()
    binding=json.loads((project/'standalone/operation.json').read_text())['demo']
    assert binding['tool_root'].startswith('../../../demo-tools/')
    assert read_deployment(project/'values.yaml').demoInfrastructure is None
    demo=read_deployment(project/'values.yaml',overlays=[project/'demo-values.yaml'])
    assert demo.operation.database=='demo' and demo.databases['demo'].credentialsSecret.name.endswith('-demo-database')
    assert demo.databases['demo'].credentialsSecret!=demo.databases['default'].credentialsSecret


def test_changed_fixture_and_conflicting_links_are_unavailable(tmp_path):
    root,project,assets=operation(tmp_path)
    (assets/'fixtures.json').write_bytes(b'changed')
    report=prepare_operation_demo(project,root,'INTERNET/Example')
    assert report['status']=='unavailable' and 'changed' in report['issues'][0]


def test_cross_operation_fixture_path_is_rejected(tmp_path):
    root,project,assets=operation(tmp_path)
    path=demo_artifact(project,'operation-demo-scenarios.json');definition=json.loads(path.read_text())
    definition['scenarios'][0]['input_xml']['asset_root']='../Other/src/test/resources'
    path.write_text(json.dumps(definition))
    assert 'not part of the assembled' in prepare_operation_demo(project,root,'INTERNET/Example')['issues'][0]


def compile_launcher(project, *, swallow=False):
    repository=Path.home()/'.m2/repository/com/fasterxml/jackson/core'
    jars=[repository/name/'2.18.2'/(name+'-2.18.2.jar') for name in ('jackson-databind','jackson-core','jackson-annotations')]
    cp=os.pathsep.join(map(str,jars))
    source=project/'Example.java'
    source.write_text('''import java.sql.*;
public class Example {
 public String execute(String xml, Connection connection) throws Exception {
  try (PreparedStatement query=connection.prepareStatement("SELECT Value FROM T WHERE Id = ?")) {
   query.setInt(1,7);
   try (ResultSet rows=query.executeQuery()) { rows.next(); return "<Result>"+rows.getString(1)+"</Result>"; }
  }'''+(' catch (SQLException failure) { return "<HandledError/>"; }' if swallow else '')+'''
 }
}''',encoding='utf-8')
    classes=project/'target/standalone-classes';classes.mkdir(parents=True)
    result=subprocess.run(['javac','-encoding','UTF-8','-cp',cp,'-d',str(classes),
        *map(str,(project/'standalone').glob('*.java')),str(source)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    return ['java','-Dfile.encoding=UTF-8','-cp',str(classes)+os.pathsep+cp,'StandaloneLaunch',str(project/'standalone/operation.json')]


def test_actual_external_launcher_uses_prebuilt_server_and_driver(tmp_path):
    root,project,assets=operation(tmp_path/'path with spaces')
    prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert prepared['status']=='prepared',prepared
    command=compile_launcher(project)
    demo_workspace(project).rename(tmp_path/'converter-records-not-shipped')
    protected={p:file_hash(p) for p in [root/'runtime-config.json',*assets.iterdir()]}
    result=subprocess.run([*command,'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=70)
    assert result.returncode==0,result.stderr
    assert result.stdout=='<Result>saved-value</Result>'
    report=json.loads((project/'standalone/.demo-runtime/last-run.json').read_text())
    assert report['status']=='completed' and not report['replay']['failed']
    state=json.loads((project/'standalone/.demo-runtime/server.json').read_text())
    assert state['status']=='stopped'
    assert not list((project/'standalone/.demo-runtime').glob('runtime-*.json'))
    assert {p:file_hash(p) for p in protected}==protected
    conflict=subprocess.run([*command,'-','--demo','--database','default'],input='<Request/>',capture_output=True,text=True,timeout=15)
    assert conflict.returncode!=0 and conflict.stdout==''


def test_launcher_rejects_changed_tool_before_starting(tmp_path):
    root,project,_=operation(tmp_path)
    report=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert report['status']=='prepared',report
    command=compile_launcher(project)
    (root/'demo-tools'/PINNED_BUNDLE/'jdbc/fixture-jdbc-driver.jar').write_bytes(b'changed')
    result=subprocess.run([*command,'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=20)
    assert result.returncode!=0 and not (project/'standalone/.demo-runtime/server.json').exists()


def test_ordered_values_reject_production_fixture_and_secret_inheritance(tmp_path):
    root,project,_=operation(tmp_path)
    assert prepare_operation_demo(project,root,'INTERNET/Example')['status']=='prepared'
    base=project/'values.yaml';overlay=project/'demo-values.yaml'
    raw=yaml.safe_load(overlay.read_text());raw['databases']['demo']['credentialsSecret']={'name':'example-database'}
    overlay.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError,match='separate credential'):read_deployment(base,overlays=[overlay])
    raw=yaml.safe_load(base.read_text());raw['databases']['default'].update(jdbcUrl='jdbc:fixtures://localhost:15432/success',
        driverClass='il.co.dcd.fixtures.jdbc.FixtureDriver')
    base.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError,match='Production values'):read_deployment(base)


def test_duplicate_yaml_keys_are_rejected(tmp_path):
    path=tmp_path/'values.yaml';path.write_text('image: {}\nimage: {}\n')
    with pytest.raises(ValueError,match='unique string'):read_deployment(path)


def test_common_jar_separate_image_contexts_and_production_excludes_fixture_bytes(tmp_path):
    root,project,_=operation(tmp_path)
    assert prepare_operation_demo(project,root,'INTERNET/Example')['status']=='prepared'
    (project/'target').mkdir()
    with ZipFile(project/'target/application.jar','w') as jar:
        jar.writestr('example.txt',b'common validated bytes')
        jar.writestr('org/springframework/boot/loader/launch/PropertiesLauncher.class',b'inventory fixture')
        jar.writestr('META-INF/MANIFEST.MF','Start-Class: example.Application\n')
    prod=read_deployment(project/'values.yaml');demo=read_deployment(project/'values.yaml',overlays=[project/'demo-values.yaml'])
    production=stage_image_variant(project,prod);demonstration=stage_image_variant(project,demo,variant='demo')
    assert production['application_sha256']==demonstration['application_sha256']
    a,b=Path(production['context']),Path(demonstration['context'])
    assert not (a/'jdbc').exists() and (b/'jdbc/jdbc-driver.jar').is_file()
    assert not list(a.rglob('*fixture*'))
    assert 'PropertiesLauncher' in (a/'Dockerfile').read_text()
    assert production['launcher']==demonstration['launcher']
    server=stage_server_image(project,demo,project)
    assert not list(Path(server['context']).rglob('fixtures.json'))
    (b/'jdbc/jdbc-driver.jar').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Immutable image context'):stage_image_variant(project,demo,variant='demo')


def test_demo_helm_real_lint_render_schema_and_merge(tmp_path):
    from tools.deployment_tools.helm_renderer import render_helm
    from tools.deployment_tools.helm_validation import validate_helm
    root,project,_=operation(tmp_path)
    assert prepare_operation_demo(project,root,'INTERNET/Example')['status']=='prepared'
    path=project/'demo-values.yaml';overlay=yaml.safe_load(path.read_text())
    overlay['image'].update(repository='example.invalid/demo',digest='sha256:'+'a'*64)
    overlay['demoInfrastructure'].update(enabled=True,fixtureClaim='saved-fixtures',fixtureMount='/fixtures',
        catalogueInContainer='/fixtures/catalogue.json',fixtureRoots=['/fixtures/assets'],
        assetRootMap={str(project.resolve()):'/fixtures/assets'},repository='example.invalid/server',digest='sha256:'+'b'*64)
    path.write_text(yaml.safe_dump(overlay));spec=read_deployment(project/'values.yaml',overlays=[path])
    (project/'target').mkdir();(project/'target/app.jar').write_bytes(b'fixture')
    chart,_=render_helm(project,spec,values_path=project/'values.yaml',overlays=[path])
    report=validate_helm(chart,spec,values_path=project/'values.yaml',overlays=[path])
    assert report['helm_passed']
    docs=list(yaml.safe_load_all(report['commands'][1]['stdout']))
    deploy=next(d for d in docs if d['kind']=='Deployment')
    assert len(deploy['spec']['template']['spec']['containers'])==2
    runtime=next(d for d in docs if d['kind']=='ConfigMap')['data']['application.yaml']
    assert 'demoInfrastructure' not in runtime and 'jdbc:fixtures:' in runtime
