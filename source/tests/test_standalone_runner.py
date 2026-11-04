"""Standalone packaging and execution preserve generated business code."""

import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from runtime.behavior_conversion.standalone_runner import write_standalone_runner


def test_packaging_preserves_configuration_and_operation_sources(tmp_path):
    root = tmp_path / "generated"
    root.mkdir()
    config = root / "runtime-config.json"
    config.write_text('{"databases":{"custom":{"password":"preserved"}}}')
    original = config.read_bytes()
    for channel in ("INTERNET", "SME"):
        project = root / channel / "Example"
        project.mkdir(parents=True)
        java = project / "Operation.java"
        java.write_text("unchanged")
        write_standalone_runner(project, root, SimpleNamespace(service_api=SimpleNamespace(type_name="Example")))
        binding = json.loads((project / "standalone/operation.json").read_text())
        assert binding['database'] == 'default'
        assert (project / "standalone" / binding['runtime_config']).resolve() == config
        assert (project / "run-operation.bat").exists()
        assert java.read_text() == "unchanged"
        assert not (project / "pom.xml").exists()
    assert config.read_bytes() == original


@pytest.fixture(scope="module")
def launcher_classes(tmp_path_factory):
    directory = tmp_path_factory.mktemp("standalone-java")
    repository = Path.home() / ".m2/repository/com/fasterxml/jackson/core"
    jars = [repository / name / '2.18.2' / (name + '-2.18.2.jar')
            for name in ('jackson-databind', 'jackson-core', 'jackson-annotations')]
    assert all(p.exists() for p in jars), "Existing shared Jackson dependencies are required"
    import os
    classpath = os.pathsep.join(map(str, jars))
    templates = Path(__file__).resolve().parents[1] / 'templates/native_operations/standalone'
    for name in ('RuntimeDatabase.java', 'StandaloneOperationRunner.java'):
        shutil.copyfile(templates / name, directory / name)
    (directory / 'FixtureOperation.java').write_text('''
public class FixtureOperation {
 public FixtureOperation(Step step) { }
 public String execute(String xml, java.sql.Connection connection) throws Exception {
  if (connection.isClosed()) throw new IllegalStateException();
  System.out.println("operation diagnostic");
  return xml;
 }
 public static class Step { public Step() { } }
}
''')
    (directory / 'FixtureDriver.java').write_text(DRIVER)
    subprocess.run(['javac', '-encoding', 'UTF-8', '-cp', classpath,
                    *map(str, directory.glob('*.java'))], check=True, capture_output=True, text=True)
    return directory, str(directory) + os.pathsep + classpath


@pytest.mark.parametrize('database_name,override', [(None,None), ('selected',None), ('wrong','selected')])
def test_xml_stdin_connection_configuration_and_close(launcher_classes, database_name, override):
    directory, classpath = launcher_classes
    config = directory / 'runtime-config.json'
    selected = 'selected' if database_name else 'default'
    config.write_text(json.dumps({'databases': {selected: {
        'ip': 'host', 'port': 2345, 'schema': 'schema', 'user': 'test-user',
        'password': 'test-password', 'jdbc_url': 'jdbc:fixture:{ip}:{port}/{schema}',
        'driver_class': 'FixtureDriver'}}}))
    binding = directory / 'operation.json'
    settings = {'service_class': 'FixtureOperation', 'runtime_config': config.name}
    if database_name is not None:
        settings['database'] = database_name
    binding.write_text(json.dumps(settings))
    closed = directory / 'closed.txt'
    xml = '<Request>value</Request>'
    result = subprocess.run(['java', '-Dclosed.file=' + str(closed), '-cp', classpath,
        'StandaloneOperationRunner', str(binding), '-', *(['--database',override] if override else [])],
        input=xml, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == xml
    assert 'operation diagnostic' in result.stderr
    assert closed.read_text() == 'closed'


def test_unknown_configured_database_does_not_fall_back(launcher_classes):
    directory, classpath = launcher_classes
    config = directory / 'unknown-database-config.json'
    config.write_text(json.dumps({'databases': {'default': {
        'jdbc_url':'jdbc:fixture:host:2345/schema', 'user':'test-user',
        'password':'test-password', 'driver_class':'FixtureDriver'}}}))
    binding = directory / 'unknown-database-operation.json'
    binding.write_text(json.dumps({'service_class':'FixtureOperation',
        'runtime_config':config.name, 'database':'unknown'}))
    result = subprocess.run(['java', '-cp', classpath, 'StandaloneOperationRunner', str(binding), '-'],
        input='<Request/>', capture_output=True, text=True)
    assert result.returncode != 0
    assert result.stdout == ''


def test_connection_failure_does_not_print_credentials(launcher_classes):
    directory, classpath = launcher_classes
    config = directory / 'bad-config.json'
    config.write_text(json.dumps({'databases': {'default': {
        'jdbc_url': 'jdbc:fixture:wrong', 'driver_class': 'FixtureDriver',
        'password': 'test-password'}}}))
    binding = directory / 'operation.json'
    binding.write_text(json.dumps({'service_class': 'FixtureOperation', 'runtime_config': config.name}))
    result = subprocess.run(['java', '-cp', classpath, 'StandaloneOperationRunner',
        str(binding), '-'], input='<Request/>', capture_output=True, text=True)
    assert result.returncode != 0
    assert result.stdout == ''
    assert 'test-password' not in result.stderr


DRIVER = '''
import java.sql.*;
import java.util.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.logging.Logger;
public class FixtureDriver implements Driver {
 static { try { DriverManager.registerDriver(new FixtureDriver()); } catch(Exception e) { throw new RuntimeException(e); } }
 public Connection connect(String url, Properties properties) throws SQLException {
  if (!acceptsURL(url)) return null;
  if (!url.equals("jdbc:fixture:host:2345/schema") || !"test-user".equals(properties.getProperty("user"))
      || !"test-password".equals(properties.getProperty("password"))) throw new SQLException("test-password");
  return (Connection)Proxy.newProxyInstance(getClass().getClassLoader(), new Class[]{Connection.class}, (p,m,a)-> {
   if (m.getName().equals("close")) {
    String file=System.getProperty("closed.file"); if(file!=null) Files.writeString(Path.of(file),"closed"); return null;
   }
   if (m.getName().equals("isClosed")) return false;
   if (m.getName().equals("prepareCall")) return Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{CallableStatement.class},(s,f,b)-> {
    if (f.getName().equals("getString")) return "NOT_FOUND";
    if (f.getReturnType()==boolean.class) return false;
    if (f.getReturnType()==int.class) return 0;
    return null;
   });
   if (m.getReturnType()==boolean.class) return false;
   if (m.getReturnType()==int.class) return 0;
   return null;
  });
 }
 public boolean acceptsURL(String url) { return url.startsWith("jdbc:fixture:"); }
 public DriverPropertyInfo[] getPropertyInfo(String url,Properties p){return new DriverPropertyInfo[0];}
 public int getMajorVersion(){return 1;} public int getMinorVersion(){return 0;}
 public boolean jdbcCompliant(){return false;} public Logger getParentLogger(){return Logger.getGlobal();}
}
'''
