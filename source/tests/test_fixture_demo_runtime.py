"""External launch failures and real Boot/Hikari driver loading use the pinned Plan A release."""
import json
import os
from pathlib import Path
import socket
import subprocess
import pytest
from runtime.fixture_demo.preparation import prepare_operation_demo,PINNED_BUNDLE
from runtime.fixture_demo.artifact_paths import demo_artifact
from runtime.fixture_jdbc_tools.releases import locate_release
from test_fixture_demo import operation,compile_launcher,free_port


def test_busy_port_is_not_killed_or_reused(tmp_path):
    root,project,_=operation(tmp_path)
    with socket.socket() as other:
        other.bind(('127.0.0.1',0));other.listen()
        port=other.getsockname()[1]
        prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=port)
        assert prepared['status']=='prepared',prepared
        result=subprocess.run([*compile_launcher(project),'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=35)
        assert result.returncode!=0 and result.stdout==''
        assert other.getsockname()[1]==port
        assert not (project/'standalone/.demo-runtime/server.json').exists()
        assert json.loads((project/'standalone/.demo-runtime/last-run.json').read_text())['status']=='execution_failed'


def test_normal_mode_keeps_demo_driver_off_the_application_classpath(tmp_path):
    root,project,_=operation(tmp_path)
    command=compile_launcher(project)
    (project/'Example.java').write_text('''public class Example {
 public String execute(String xml) throws Exception {
  try {Class.forName("il.co.dcd.fixtures.jdbc.FixtureDriver");throw new AssertionError("Demo driver leaked");}
  catch(ClassNotFoundException expected) {return xml;}
 }
}''')
    subprocess.run(['javac','-d',str(project/'target/standalone-classes'),str(project/'Example.java')],
        check=True,capture_output=True,text=True,timeout=30)
    result=subprocess.run([*command,'-'],input='<Normal/>',capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and result.stdout=='<Normal/>',result.stderr
    assert not (project/'standalone/.demo-runtime').exists()


def test_changed_operation_inputs_cannot_reuse_old_demo_preparation(tmp_path):
    root,project,_=operation(tmp_path)
    marker=project/'src/main/resources/operation-settings.txt';marker.parent.mkdir(parents=True)
    marker.write_text('frozen')
    prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert prepared['status']=='prepared',prepared
    command=compile_launcher(project)
    good=subprocess.run([*command,'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=60)
    assert good.returncode==0,good.stderr
    state=project/'standalone/.demo-runtime/server.json';before=state.read_bytes()
    marker.write_text('changed')
    bad=subprocess.run([*command,'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=20)
    assert bad.returncode!=0 and bad.stdout==''
    assert state.read_bytes()==before


def test_caught_fixture_miss_remains_a_failed_demo(tmp_path):
    root,project,assets=operation(tmp_path)
    definition=demo_artifact(project,'operation-demo-scenarios.json')
    # Retain a valid resource whose SQL deliberately differs from the executed call.
    from runtime.test_assets.store import publish
    from models.shared_test_fixture import SharedFixtureBank
    from models.junit_test_scenario import JunitScenarioSuite
    from models.comparison_test_scenario import ComparisonScenarioSuite
    from runtime.fixture_jdbc_tools.releases import digest
    bank=SharedFixtureBank(fixtures={'request':dict(kind='xml',value='<Request/>'),
        'database':dict(kind='database',value=dict(queries=[dict(sql='SELECT Different',parameters=[],columns=['Value'],rows=[['x']])]))})
    path,manifest=publish(project/'src/test/resources/shared-test-assets','INTERNET/Example',{'negative':'fixture miss'},
        bank,JunitScenarioSuite(scenarios=[dict(scenario_id='definition',purpose='Saved data',
            native_entry=dict(owner_type='java.lang.String',method_name='isEmpty'),assertions=['definition'])]),ComparisonScenarioSuite())
    raw=json.loads(definition.read_text())
    for reference in [raw['scenarios'][0]['input_xml'],*raw['scenarios'][0]['resources']['database']]:
        reference.update(asset_root=path.relative_to(project).as_posix(),manifest_hash=digest(manifest.model_dump(mode='json')))
    definition.write_text(json.dumps(raw))
    report=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert report['status']=='prepared',report
    result=subprocess.run([*compile_launcher(project,swallow=True),'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=60)
    assert result.stdout=='<HandledError/>' and result.returncode!=0,result.stderr
    report=json.loads((project/'standalone/.demo-runtime/last-run.json').read_text())
    assert report['status']=='execution_failed' and report['replay']['failed']


def test_reused_server_survives_until_explicit_stop_and_clean(tmp_path):
    root,project,_=operation(tmp_path)
    prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert prepared['status']=='prepared',prepared
    binding=json.loads((project/'standalone/operation.json').read_text())['demo']
    state=project/'standalone/.demo-runtime';release,_=locate_release(PINNED_BUNDLE)
    command=['java','-jar',str(release/'server/fixture-server.jar')]
    ensured=[*command,'ensure','--jdbc-url',binding['jdbc_url'],'--catalogue',prepared['catalogue'],
        '--expected-hash',prepared['catalogue_hash'],'--fixture-root',str(root),'--state-dir',str(state)]
    subprocess.run(ensured,check=True,capture_output=True,text=True,timeout=30)
    try:
        launcher=compile_launcher(project)
        result=subprocess.run([*launcher,'-','--demo'],input='<Request/>',capture_output=True,text=True,timeout=60)
        assert result.returncode==0,result.stderr
        assert json.loads(subprocess.run([*command,'status','--state-dir',str(state)],check=True,
            capture_output=True,text=True,timeout=15).stdout)['ready']
        # Ownership is outside target and survives the existing batch's Maven clean.
        import shutil
        target=(project/'target').resolve();assert target.is_relative_to(project.resolve())
        shutil.rmtree(target)
        launcher=compile_launcher(project)
        stopped=subprocess.run([*launcher,'--demo-stop'],capture_output=True,text=True,timeout=30)
        assert stopped.returncode==0,stopped.stderr
    finally:
        subprocess.run([*command,'stop','--state-dir',str(state)],capture_output=True,text=True,timeout=15)


def test_properties_launcher_loads_external_driver_through_real_hikari(tmp_path):
    """Use the saved executable's libraries without changing its bytes or business classes."""
    root,project,_=operation(tmp_path)
    prepared=prepare_operation_demo(project,root,'INTERNET/Example',port=free_port());assert prepared['status']=='prepared',prepared
    saved=Path('outputs/getclientlinks-microservice-20261104/services/INTERNET/GetClientLinksOp/target')
    jars=list(saved.glob('*.jar'))
    if not jars:pytest.skip('Saved executable service is not available in this checkout')
    jar=jars[0].resolve();release,_=locate_release(PINNED_BUNDLE)
    import zipfile,hashlib
    original=hashlib.sha256(jar.read_bytes()).hexdigest()
    libs=tmp_path/'compile-libs';libs.mkdir()
    with zipfile.ZipFile(jar) as application:
        for name in application.namelist():
            if name.startswith('BOOT-INF/lib/') and name.endswith('.jar'):
                (libs/Path(name).name).write_bytes(application.read(name))
    source=tmp_path/'PoolProbe.java'
    source.write_text('''import com.zaxxer.hikari.*;
public class PoolProbe {
 public static void main(String[] args) throws Exception {
  HikariConfig config=new HikariConfig(); config.setJdbcUrl(args[0]);
  config.setDriverClassName("il.co.dcd.fixtures.jdbc.FixtureDriver");
  config.setMinimumIdle(0);config.setMaximumPoolSize(2);
  try(HikariDataSource pool=new HikariDataSource(config)) {
   for(int i=0;i<3;i++) try(var connection=pool.getConnection();var query=connection.prepareStatement("SELECT Value FROM T WHERE Id = ?")) {
    query.setInt(1,7);try(var rows=query.executeQuery()) { rows.next();if(!rows.getString(1).equals("saved-value"))throw new AssertionError(); }
   }
   System.out.print("external-driver-hikari-passed");
  }
 }
}''',encoding='utf-8')
    classes=tmp_path/'probe';classes.mkdir()
    built=subprocess.run(['javac','-cp',str(libs/'*'),'-d',str(classes),str(source)],capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stderr
    state=tmp_path/'server-state';url=f'jdbc:fixtures://127.0.0.1:{json.loads((project/"standalone/operation.json").read_text())["demo"]["jdbc_url"].split(":")[3].split("/")[0]}/success?resource=database&execution=boot-probe'
    server=['java','-jar',str(release/'server/fixture-server.jar')]
    subprocess.run([*server,'ensure','--jdbc-url',url,'--catalogue',prepared['catalogue'],
        '--expected-hash',prepared['catalogue_hash'],'--fixture-root',str(root),'--state-dir',str(state)],check=True,capture_output=True,text=True,timeout=30)
    try:
        result=subprocess.run(['java','-Dloader.path='+str(classes)+','+str(release/'jdbc/fixture-jdbc-driver.jar'),
            '-Dloader.main=PoolProbe','-cp',str(jar),'org.springframework.boot.loader.launch.PropertiesLauncher',url],
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,result.stderr
        assert 'external-driver-hikari-passed' in result.stdout
        report=json.loads(subprocess.run([*server,'report','--state-dir',str(state),'--execution','boot-probe'],
            check=True,capture_output=True,text=True,timeout=15).stdout)
        assert not report['failed']
    finally:subprocess.run([*server,'stop','--state-dir',str(state)],capture_output=True,text=True,timeout=15)
    assert hashlib.sha256(jar.read_bytes()).hexdigest()==original
