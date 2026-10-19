"""Exercise loaded channel services, configured lookups and secret-free connector evidence."""

from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.component_inventory_tools.java_service_lookups import service_lookups


def workspace(tmp_path):
    project = tmp_path / 'Project'
    src = project / 'src'
    channel = src / 'Xml Definition/Channel/INTERNET'
    definitions = channel / 'defaultFile'
    definitions.mkdir(parents=True)
    (src / 'example').mkdir()
    (project / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/><classpathentry kind="lib" path="driver.jar"/></classpath>')
    registry = '''<dse.ini><kColl id="settings"><kColl id="files"><kColl id="defaultFile">
    <operDef id="defaultFile/services.tmp"/><operDef id="defaultFile/connectors.tmp"/>
    </kColl></kColl><kColl id="tags"><kColl id="services">
    <field id="RegularService" value="example.RegularService"/>
    <field id="TransactionService" value="example.TransactionService"/>
    </kColl></kColl></kColl></dse.ini>'''
    (channel / 'dse.ini').write_text(registry)
    (definitions / 'services.tmp').write_text('''<XML>
    <RegularService id="regular" poolName="pool"/>
    <TransactionService id="transaction" autoCommit="false" poolName="pool"/>
    </XML>''')
    (definitions / 'connectors.tmp').write_text('''<XML><JDBCServicesConnectionManagerIDB id="manager">
    <column id="pool" dbType="Oracle" JDBCDriver="example.Driver" databaseURL="jdbc:oracle:thin:privateEndpoint"
    user="privateUser" password="privatePassword" size="10"/>
    </JDBCServicesConnectionManagerIDB></XML>''')
    (src / 'example/RegularService.java').write_text('package example; public class RegularService { public Object getConnection() { return null; } }')
    (src / 'example/TransactionService.java').write_text('package example; public class TransactionService extends RegularService { private Object connection; }')
    with ZipFile(project / 'driver.jar', 'w') as jar:
        jar.writestr('example/Driver.class', b'class fixture')
        jar.writestr('META-INF/maven/example/vendor-driver/pom.properties', 'groupId=example\nartifactId=vendor-driver\nversion=1.2.3\n')
    return tmp_path, src, channel, definitions


def resolve(root, code, params=None, channel='INTERNET'):
    return resolve_service_connections(root, channel, {'example.Step': code}, params or {},
        discover_java_sources(str(root)), discover_java_classpath(str(root)))


def test_channel_service_pool_and_driver_are_resolved_from_loaded_nonxml_files(tmp_path):
    root, _, _, _ = workspace(tmp_path)
    record, = resolve(root, 'getContext().getService("transaction");')
    assert not record.issues
    assert record.database_type == 'Oracle'
    assert record.driver_class == 'example.Driver'
    assert record.driver_dependency['version'] == '1.2.3'
    assert record.configuration['autoCommit'] == 'false'
    assert len(record.supporting_sources) == 2
    data = record.model_dump_json()
    assert all(secret not in data for secret in ['privatePassword', 'privateUser', 'privateEndpoint'])


def test_configured_parameter_and_supplied_conditional_helper_select_one_service(tmp_path):
    root, _, _, _ = workspace(tmp_path)
    source = '''class Step {
      void execute() {
        boolean global = false;
        global = isGlobalConnection();
        if (global) { getContext().getService("transaction"); }
        else { getContext().getService("regular"); }
      }
      boolean isGlobalConnection() {
        String spService = (String) getParams().tryGetValueAt("spService");
        if (spService != null && spService.equals("transaction")) return true;
        return false;
      }
    }'''
    records = resolve(root, source, {'spService': 'transaction'})
    assert [item.service_id for item in records] == ['transaction']
    assert [item.service_id for item in resolve(root, source, {'spService': 'regular'})] == ['regular']
    assert {item.service_id for item in resolve(root, source)} == {'regular', 'transaction'}


def test_comments_case_and_dynamic_lookup_are_not_guessed(tmp_path):
    root, _, _, _ = workspace(tmp_path)
    assert resolve(root, '// getService("regular");') == []
    wrong, = resolve(root, 'getService("REGULAR");')
    assert any('Missing or ambiguous service instance' in item for item in wrong.issues)
    dynamic, = resolve(root, 'getService(request.getServiceName());')
    assert dynamic.issues and dynamic.driver_dependency is None
    assert service_lookups('getService(getParams().tryGetValueAt("service"));', {'service': 'regular'})[0]['service_name'] == 'regular'
    assert service_lookups('String name="regular"; name=request.name(); getService(name);', {})[0]['service_name'] is None
    assert service_lookups('client.getService("regular");', {}) == []


def test_unloaded_file_and_other_channel_do_not_override_connector(tmp_path):
    root, src, channel, definitions = workspace(tmp_path)
    (definitions / 'unused.xml').write_text('<XML><column id="pool" dbType="MySQL" JDBCDriver="wrong.Driver"/></XML>')
    another = channel.parent / 'OTHER/defaultFile'
    another.mkdir(parents=True)
    (another.parent / 'dse.ini').write_text((channel / 'dse.ini').read_text())
    for name in ['services.tmp', 'connectors.tmp']:
        (another / name).write_text((definitions / name).read_text().replace('Oracle', 'MySQL'))
    assert resolve(root, 'getService("regular");')[0].database_type == 'Oracle'
    assert resolve(root, 'getService("regular");', channel='OTHER')[0].database_type == 'MySQL'


def test_channel_imports_local_override_and_missing_pool_are_explicit(tmp_path):
    root, _, channel, definitions = workspace(tmp_path)
    (definitions / 'services.tmp').write_text('<XML><RegularService id="regular" poolName="absent"/></XML>')
    result, = resolve(root, 'getService("regular");')
    assert any('connector pool: absent' in item for item in result.issues)
    (channel / 'dse.ini').write_text('<dse.ini><kColl id="import"><field id="INTERNET"/></kColl></dse.ini>')
    assert 'import cycle' in resolve(root, 'getService("regular");')[0].issues[0]
