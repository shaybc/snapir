"""Use the real Python asset publisher to verify the independent Java read-only loader."""
import hashlib
import json
import subprocess
from pathlib import Path
import pytest
from runtime.fixture_jdbc_tools.releases import digest
from runtime.test_assets.references import resolve
from models.shared_test_fixture import SharedFixtureBank
from fixture_jdbc_support import assets, command, ensure, source_root, compile_client


def test_actual_python_bank_unicode_xml_nulls_and_nested_references(tmp_path):
    catalogue, definition, root = assets(tmp_path)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    reference = definition['scenarios']['success']['resources']['database']['fixtures'][0]
    reference.update(fixture_id='pointer', pointer='/a~1b/~0value')
    catalogue.write_text(json.dumps(definition, ensure_ascii=False), encoding='utf-8')
    result = command('verify-fixtures', '--catalogue', catalogue, '--expected-hash', digest(definition), '--fixture-root', tmp_path)
    assert json.loads(result.stdout)['catalogue_hash'] == digest(definition)
    bank = SharedFixtureBank.model_validate_json((root / 'fixtures.json').read_text(encoding='utf-8'))
    assert resolve(bank, dict(fixture_id='xml')) == '\ufeff<x>\r\nשלום 😀</x>'
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}


@pytest.mark.parametrize('problem', ['document_changed', 'manifest_changed', 'catalogue_hash', 'cyclic', 'missing_pointer', 'outside_root', 'conflict'])
def test_invalid_or_conflicting_saved_evidence_is_rejected(tmp_path, problem):
    catalogue, definition, root = assets(tmp_path)
    reference = definition['scenarios']['success']['resources']['database']['fixtures'][0]
    expected = digest(definition)
    if problem == 'document_changed':
        with (root / 'fixtures.json').open('ab') as stream:
            stream.write(b'\r\n')
    elif problem == 'manifest_changed':
        content = json.loads((root / 'manifest.json').read_text())
        content['boundary_identity'] = 'another-boundary'
        (root / 'manifest.json').write_text(json.dumps(content))
    elif problem == 'catalogue_hash':
        expected = '0' * 64
    elif problem == 'missing_pointer':
        reference['pointer'] = '/absent'
    elif problem in ('cyclic', 'conflict'):
        fixture = json.loads((root / 'fixtures.json').read_text(encoding='utf-8'))
        if problem == 'cyclic':
            fixture['fixtures']['alias']['value'] = {'$fixture': 'alias'}
        else:
            duplicate = dict(fixture['fixtures']['database']['value']['queries'][0], rows=[['different', None]])
            fixture['fixtures']['database']['value']['queries'].append(duplicate)
        raw = json.dumps(fixture, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
        (root / 'fixtures.json').write_bytes(raw)
        manifest = json.loads((root / 'manifest.json').read_text())
        manifest['files']['fixtures.json'] = hashlib.sha256(raw).hexdigest()
        (root / 'manifest.json').write_text(json.dumps(manifest))
        reference['manifest_hash'] = digest(manifest)
    if problem not in ('catalogue_hash', 'document_changed', 'manifest_changed'):
        expected = digest(definition)
    catalogue.write_text(json.dumps(definition), encoding='utf-8')
    allowed = tmp_path / 'not-the-assets' if problem == 'outside_root' else tmp_path
    allowed.mkdir(exist_ok=True)
    assert command('verify-fixtures', '--catalogue', catalogue, '--expected-hash', expected, '--fixture-root', allowed, check=False).returncode != 0


def test_shaded_driver_over_real_port_and_sticky_reports(tmp_path):
    url, state, _, receipt = ensure(tmp_path)
    driver = source_root() / 'jdbc-fixture-java/fixture-driver/target/fixture-jdbc-driver-1.0.0-standalone.jar'
    source = '''import java.sql.*;
public class Probe {
  public static void main(String[] args) throws Exception {
    if (DriverManager.getDriver(args[0]).getClass().getName().equals("il.co.dcd.fixtures.jdbc.FixtureDriver") == false) throw new AssertionError();
    try(Connection c=DriverManager.getConnection(args[0]);PreparedStatement p=c.prepareStatement("SELECT Value FROM T WHERE Id = ?")) {
      p.setInt(1,7);try(ResultSet r=p.executeQuery()){if(!r.next()||!r.getString("Value").equals("שלום\\r\\n😀<x>"))throw new AssertionError();}
      try(CallableStatement call=c.prepareCall("{call TEST(?,?,?)}")){call.setString(1,"C");call.registerOutParameter(2,Types.VARCHAR);call.registerOutParameter(3,Types.REF_CURSOR);call.execute();if(!"210".equals(call.getString(2)))throw new AssertionError();}
      try(PreparedStatement missing=c.prepareStatement("SELECT NoFixture")){try{missing.executeQuery();throw new AssertionError();}catch(SQLException expected){if(!"FXMIS".equals(expected.getSQLState()))throw expected;}}
    }
    System.out.print("matched");
  }
}'''
    try:
        invocation = compile_client(tmp_path, source, driver)
        result = subprocess.run([*invocation, url], capture_output=True, encoding='utf-8', timeout=30)
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'matched'
        report = json.loads(command('report', '--state-dir', state, '--execution', 'acceptance').stdout)
        assert report['failed'] is True and any(e.get('code') == 'FIXTURE_MISS' for e in report['events'])
    finally:
        command('stop', '--state-dir', state, check=False)
    assert json.loads(command('report', '--state-dir', state, '--execution', 'acceptance').stdout)['failed'] is True


def test_existing_harness_facade_owns_proxies_and_reuses_canonical_values(tmp_path):
    harness = source_root() / 'behavior-verification-java/target/behavior-verification-1.0.0-jar-with-dependencies.jar'
    assert harness.is_file(), 'Build the copied existing harness for facade regression'
    source = '''import java.sql.*; import java.util.*;
import il.co.dcd.verification.fixtures.*;
public class Probe {
  public static void main(String[] args) throws Exception {
    var q=Map.<String,Object>of("sql","SELECT X", "parameters",List.of(7), "columns",List.of("ExactCase"), "rows",List.of(List.of("9")));
    FixtureResources.reset(Map.of("resources",Map.of("db",Map.of("queries",List.of(q)))));
    try(Connection c=(Connection)FixtureResources.resource("db")) {
      if(FixtureResources.checked(c)!=c)throw new AssertionError();
      try(PreparedStatement p=c.prepareStatement("SELECT X")){p.setLong(1,7);try(ResultSet r=p.executeQuery()){if(!r.next()||r.getInt("ExactCase")!=9)throw new AssertionError();}}
      try(PreparedStatement p=c.prepareStatement("SELECT Missing")){try{p.executeQuery();throw new AssertionError();}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}}
    }finally{FixtureResources.clear();}
    System.out.print("facade-preserved");
  }
}'''
    invocation = compile_client(tmp_path, source, harness)
    result = subprocess.run(invocation, capture_output=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'facade-preserved'


def test_explicit_root_relocation_keeps_the_original_catalogue_and_bank_hashes(tmp_path):
    catalogue, definition, root = assets(tmp_path)
    ref = definition['scenarios']['success']['resources']['database']['fixtures'][0]
    original = 'X:/old-fixture-volume'
    ref['asset_root'] = original
    catalogue.write_text(json.dumps(definition), encoding='utf-8')
    before = catalogue.read_bytes()
    args = ('verify-fixtures', '--catalogue', catalogue, '--expected-hash', digest(definition), '--fixture-root', tmp_path)
    assert command(*args, check=False).returncode != 0
    assert command(*args, '--asset-root-map', original + '=' + str(root)).returncode == 0
    assert catalogue.read_bytes() == before


def test_duplicate_numeric_input_references_deduplicate_but_do_not_change_results(tmp_path):
    from fixture_jdbc_support import queries
    values = queries()
    values.append(dict(values[0], parameters=[7.0]))
    catalogue, definition, root = assets(tmp_path, values)
    assert command('verify-fixtures', '--catalogue', catalogue, '--expected-hash', digest(definition), '--fixture-root', tmp_path).returncode == 0


@pytest.mark.parametrize('failure', [None, {'type': 'java.sql.SQLException'}, {'type': 'java.sql.SQLException', 'message': None}])
def test_existing_optional_exception_shapes_remain_compatible(tmp_path, failure):
    values = [dict(sql='SELECT X', parameters=[], columns=['X'], rows=[[1]], exception=failure)]
    catalogue, definition, root = assets(tmp_path, values)
    assert command('verify-fixtures', '--catalogue', catalogue, '--expected-hash', digest(definition), '--fixture-root', tmp_path).returncode == 0
