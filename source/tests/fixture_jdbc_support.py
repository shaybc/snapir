"""Isolated fixtures and Java processes for converter tooling acceptance, never operation conversion."""
import json
import os
import socket
import subprocess
from pathlib import Path
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from runtime.test_assets.store import publish
from runtime.fixture_jdbc_tools.releases import digest


def source_root():
    return Path(os.environ.get('FIXTURE_JDBC_TEST_SOURCE', Path(__file__).resolve().parents[1]))


def java():
    return os.environ.get('FIXTURE_JDBC_TEST_JAVA', 'java')


def server_jar():
    path = source_root() / 'jdbc-fixture-java/fixture-server/target/fixture-server-1.0.0-standalone.jar'
    assert path.is_file(), 'Build fixture tooling before running its acceptance tests'
    return path


def command(*args, check=True):
    result = subprocess.run([java(), '-jar', str(server_jar()), *map(str, args)], capture_output=True,
        encoding='utf-8', errors='replace', timeout=35)
    if check:
        assert result.returncode == 0, result.stderr
    return result


def queries():
    return [dict(sql='SELECT Value FROM T WHERE Id = ?', parameters=[7], columns=['Value', 'Optional'], rows=[['שלום\r\n😀<x>', None]], exception=None),
        dict(sql='{call TEST(?,?,?)}', parameters=['C'], out_parameters={'2': dict(sql_type=12, value='210'),
            '3': dict(sql_type=2012, columns=['Id'], rows=[[7]])}),
        dict(sql='SELECT Failure', parameters=[], exception=dict(type='java.sql.SQLException', message='prepared failure'))]


def assets(directory, values=None):
    bank = SharedFixtureBank(fixtures={
        'database': dict(kind='database', value=dict(queries=values if values is not None else queries())),
        'alias': dict(value={'$fixture': 'database'}),
        'xml': dict(kind='xml', value='\ufeff<x>\r\nשלום 😀</x>'),
        'pointer': dict(value={'a/b': {'~value': {'$fixture': 'database'}}})})
    root, manifest = publish(directory / 'existing-assets', 'generic-fixture-boundary', {'purpose': 'tool acceptance'},
        bank, JunitScenarioSuite(scenarios=[dict(scenario_id='definition', purpose='Fixture publication compatibility',
            native_entry=dict(owner_type='java.lang.String', method_name='isEmpty'), assertions=['Fixture definition only'])]), ComparisonScenarioSuite())
    catalogue = dict(schema_version='fixture-jdbc-catalogue-v1', scenarios={
        'success': dict(resources={'database': dict(fixtures=[dict(asset_root=os.path.relpath(root, directory),
            manifest_hash=digest(manifest.model_dump(mode='json')), fixture_id='alias', pointer='')])})})
    path = directory / 'catalogue.json'
    path.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2), encoding='utf-8')
    return path, catalogue, root


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def ensure(directory):
    catalogue, definition, root = assets(directory)
    port = free_port()
    url = f'jdbc:fixtures://127.0.0.1:{port}/success?execution=acceptance'
    state = directory / 'runtime state'
    args = ('ensure', '--jdbc-url', url, '--catalogue', catalogue, '--expected-hash', digest(definition),
        '--state-dir', state, '--fixture-root', directory)
    receipt = json.loads(command(*args).stdout)
    return url, state, args, receipt


def compile_client(directory, source, classpath):
    path = directory / 'Probe.java'
    path.write_text(source, encoding='utf-8')
    java_path = Path(java())
    compiler = java_path.with_name('javac.exe' if os.name == 'nt' else 'javac') if java_path.is_absolute() else Path('javac')
    result = subprocess.run([str(compiler), '-encoding', 'UTF-8', '-cp', str(classpath), '-d', str(directory), str(path)],
        capture_output=True, encoding='utf-8', errors='replace', timeout=60)
    assert result.returncode == 0, result.stderr
    return [java(), '-Dfile.encoding=UTF-8', '-cp', str(directory) + os.pathsep + str(classpath), 'Probe']
