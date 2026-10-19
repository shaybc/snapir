"""Verify configured Java driver linkage offline and approved-version fallback."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from models.service_connection import ServiceConnection
from runtime.behavior_conversion.driver_resolution import verify_driver_load, verify_connections
from runtime.java_toolchain import java_environment
from tests.runtime.test_behavior_conversion import profile


def test_real_java25_driver_probe_does_not_initialize_or_access_database(tmp_path):
    settings = profile(java_version=25, java_home='C:/Program Files/Java/jdk-25.0.3')
    environment = java_environment(settings.java_version, settings.java_home)
    source = tmp_path / 'Driver.java'
    marker = tmp_path / 'initialized.txt'
    source.write_text('''package example;
    public class Driver implements java.sql.Driver {
      static { try { java.nio.file.Files.writeString(java.nio.file.Path.of(''' + json.dumps(str(marker)) + '''), "initialized"); }
               catch (Exception e) { throw new RuntimeException(e); } }
      public java.sql.Connection connect(String u, java.util.Properties p) { throw new UnsupportedOperationException(); }
      public boolean acceptsURL(String u) { return false; }
      public java.sql.DriverPropertyInfo[] getPropertyInfo(String u, java.util.Properties p) { return new java.sql.DriverPropertyInfo[0]; }
      public int getMajorVersion() { return 1; } public int getMinorVersion() { return 0; }
      public boolean jdbcCompliant() { return false; }
      public java.util.logging.Logger getParentLogger() { return java.util.logging.Logger.getGlobal(); }
    }''')
    result = subprocess.run([str(Path(environment['JAVA_HOME']) / 'bin/javac.exe'), '-d', str(tmp_path), str(source)],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    jar = tmp_path / 'driver.jar'
    with ZipFile(jar, 'w') as output:
        output.write(tmp_path / 'example/Driver.class', 'example/Driver.class')
    verify_driver_load('example.Driver', [str(jar)], settings)
    assert not marker.exists()
    with pytest.raises(ValueError, match='cannot load on configured Java 25'):
        verify_driver_load('missing.Driver', [str(jar)], settings)


def test_verified_approved_replacement_is_selected_before_a_user_question(monkeypatch):
    first = dict(group_id='example', artifact_id='driver', version='old', scope='runtime', reason='workspace', required_classes=['example.Driver'])
    replacement = dict(first, version='verified')
    record = ServiceConnection(connection_id='resource', channel='INTERNET', service_id='service', resource_kind='jdbc',
        driver_class='example.Driver', driver_dependency=first, driver_candidates=[{'dependency': first}])
    monkeypatch.setattr('constants.SERVICE_DRIVER_DEPENDENCY_CANDIDATES', [dict(driver_class='example.Driver', java_versions=[25], dependency=replacement)])
    calls = []
    class Verifier:
        def __call__(self, dependency):
            calls.append(dependency.version)
            if dependency.version == 'old':
                raise ValueError('Old dependency unavailable')
        def resolved_runtime_classpath(self, dependency):
            return [dependency.version + '.jar']
    monkeypatch.setattr('runtime.behavior_conversion.driver_resolution.verify_driver_load',
                        lambda name, libs, settings: calls.append(libs))
    verify_connections([record], profile(java_version=25), Verifier(), SimpleNamespace(libraries=['old.jar']))
    assert record.driver_dependency['version'] == 'verified'
    assert calls == ['old', 'verified', ['verified.jar']]
    assert record.issues == []
    assert record.ownership['driver_verification']['server_compatibility'] == 'not_tested'
