"""Require executable source for every configured bank-demo implementation and its evidence."""

import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

from test_scoped_vault_identity import scoped_mapper, invoke_mapper
from test_behavior_verification_boundaries import boundary_tool


ROOT = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace'


def test_every_configured_tag_and_step_has_demo_source():
    classes = {re.search(r'package\s+([\w.]+)', path.read_text()).group(1) + '.' + path.stem
               for path in ROOT.rglob('*.java')}
    mappings = {node.get('id'): node.get('value') for path in ROOT.rglob('dse.ini')
                for node in ElementTree.parse(path).iter('field') if '.' in node.get('value', '')}
    missing = []
    for path in ROOT.rglob('*.xml'):
        for node in ElementTree.parse(path).iter():
            implementation = node.get('implClass') or mappings.get(node.tag)
            if implementation and implementation not in classes:
                missing.append((str(path), node.tag, implementation))
    assert not missing, missing
    assert not any('UnsupportedOperationException' in path.read_text() for path in ROOT.rglob('*.java'))


def test_demo_sources_compile_and_decorator_behavior_executes(tmp_path):
    harness = tmp_path / 'DemoSourceCheck.java'
    harness.write_text('''import java.util.*;
import com.ibm.dse.base.*;
import com.ibm.il.dse.cc.decorator.*;
import com.ibm.il.dse.cc.format.*;
import com.ibm.il.dse.cc.cut.CCDSEServerOperation;
public class DemoSourceCheck {
    static void check(boolean condition) { if (!condition) throw new AssertionError(); }
    static Tag tag(String... pairs) {
        Tag tag = new Tag();
        for (int i=0; i<pairs.length; i+=2) tag.setAttribute(pairs[i], pairs[i+1]);
        return tag;
    }
    static void rejected(Runnable action) {
        try { action.run(); throw new AssertionError("Missing mandatory rejection"); }
        catch (IllegalArgumentException expected) { }
    }
    public static void main(String[] args) throws Exception {
        CCMandatory mandatory = new CCMandatory();
        for (String value : new String[] {null, ""}) {
            rejected(() -> mandatory.addDecoration(value));
            rejected(() -> mandatory.removeDecoration(value));
        }
        check(" ".equals(mandatory.removeDecoration(" ")));
        CCNullToZero zero = new CCNullToZero();
        for (String value : new String[] {null, ""}) {
            check("0".equals(zero.addDecoration(value)));
            check("0".equals(zero.removeDecoration(value)));
        }
        check(" ".equals(zero.removeDecoration(" ")));
        check("007".equals(zero.removeDecoration("007")));

        CCXML request = new CCXML(); request.initializeFrom(tag("dataName", "GetAccountDetails"));
        CCString account = new CCString(); account.initializeFrom(tag("dataName", "AccountNumber"));
        CCPadding padding = new CCPadding(); padding.initializeFrom(tag("padChar", "0", "length", "10"));
        account.addDecorator(mandatory); account.addDecorator(padding); request.addChild(account);
        CCString max = new CCString(); max.initializeFrom(tag("dataName", "MaxTransactions"));
        max.addDecorator(zero); max.addDecorator(new RemoveLeadingZerosDecorator()); request.addChild(max);
        Context context = new Context();
        request.unformat("<GetAccountDetails><AccountNumber>0000012345</AccountNumber><MaxTransactions/></GetAccountDetails>", context);
        check("12345".equals(context.getValueAt("AccountNumber")));
        check("0".equals(context.getValueAt("MaxTransactions")));
        check(request.format(context).contains("<AccountNumber>0000012345</AccountNumber>"));
        try {
            request.unformat("<GetAccountDetails><AccountNumber>000</AccountNumber></GetAccountDetails>", context);
            throw new AssertionError("Mandatory must run after stripping padding");
        } catch (IllegalArgumentException expected) { }

        CCString message = new CCString(); message.initializeFrom(tag("dataName", "ErrorDescription"));
        message.addAttributeDecorator(new NilDecorator());
        context.setValueAt("CHANNEL_NAME", "INTERNET"); context.setValueAt("APPLICATION", "BANK");
        SchemaValidationSettings.configure(Set.of("internet"), Set.of());
        check(message.format(context).contains("xsi:nil=\\"true\\""));
        SchemaValidationSettings.configure(Set.of(), Set.of());
        check(!message.format(context).contains("xsi:nil"));
        context.setValueAt("ErrorDescription", "a&b");
        check(message.format(context).contains("a&amp;b"));

        CCDate date = new CCDate(); date.initializeFrom(tag("dataName", "Date", "pattern", "yyyyMMdd"));
        date.unformat("<Date>20240102</Date>", context);
        check(date.format(context).equals("<Date>20240102</Date>"));
        com.ibm.il.dse.cc.format.NumberFormat number = new com.ibm.il.dse.cc.format.NumberFormat();
        number.initializeFrom(tag("dataName", "Amount", "showThousandsSep", "yes", "decimalPlaces", "2"));
        context.setValueAt("Amount", "1234.5"); check(number.format(context).contains("1,234.50"));
        number.unformat("<Amount>1,234.50</Amount>", context);
        check("1234.50".equals(context.getValueAt("Amount").toString()));
        CCIColl collection = new CCIColl(); collection.initializeFrom(tag("dataName", "Rows", "times", "*"));
        CCXML row = new CCXML(); row.initializeFrom(tag("dataName", "Row"));
        CCString value = new CCString(); value.initializeFrom(tag("dataName", "Value")); row.addChild(value); collection.addChild(row);
        context.setValueAt("Rows", List.of(Map.of("Value", "one"), Map.of("Value", "two")));
        String rows = collection.format(context); check(rows.equals("<Row><Value>one</Value></Row><Row><Value>two</Value></Row>"));
        collection.unformat(rows, context); check(((List<?>)context.getValueAt("Rows")).size() == 2);
        CCConstant constant = new CCConstant(); constant.initializeFrom(tag("dataName", "Status", "value", "SUCCESS"));
        check("<Status>SUCCESS</Status>".equals(constant.format(context)));
        CCSysTimeDate timestamp = new CCSysTimeDate(); timestamp.initializeFrom(tag("dataName", "Timestamp"));
        check(timestamp.format(context).contains("1970-01-01T00:00:00Z"));

        CCDSEServerOperation operation = new CCDSEServerOperation(); operation.setContext(context);
        context.setValueAt("CHANNEL_NAME", "INTERNET");
        operation.setOperationFields("Initial=yes");
        CCOperationStep step = new CCOperationStep() { public int execute() { getContext().setValueAt("Visited", "yes"); return 0; } };
        operation.addOperationStep(new KeyedCollection(Map.of("id", "Skip", "onlyFor", "IVR"), step));
        operation.addOperationStep(new KeyedCollection(Map.of("id", "First", "on0Do", "Done"), step));
        operation.addOperationStep(new KeyedCollection(Map.of("id", "Done", "on0Do", "end"), step));
        operation.execute(); check("yes".equals(context.getValueAt("Visited"))); check("yes".equals(context.getValueAt("Initial")));
    }
}''')
    result = subprocess.run(['javac', '-d', str(tmp_path), *map(str, ROOT.rglob('*.java')), str(harness)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run(['java', '-cp', str(tmp_path), 'DemoSourceCheck'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_fresh_bank_units_supply_all_configured_decorator_sources(tmp_path, scoped_mapper, boundary_tool):
    from models.pipeline_configuration import PipelineConfiguration
    from tools.composer_mapper_tools.vault_importer import import_vault
    from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
    from tools.state_store_tools.db import get_connection, create_all_tables
    from runtime.behavior_conversion.behavior_extraction import evidence_catalog
    root = tmp_path / 'source'
    shutil.copytree(ROOT, root)
    vault = tmp_path / 'vault'
    result = invoke_mapper(scoped_mapper, root, vault)
    assert result.returncode == 0, result.stderr
    conn = get_connection(':memory:')
    create_all_tables(conn)
    config = SimpleNamespace(run_id='bank-source-evidence', source_root=str(root), vault_root=str(vault),
        run_mode=SimpleNamespace(value='full_inventory'), target_channels=[], include_operations=None, exclude_operations=None)
    profile = PipelineConfiguration(source_root=str(root), conversion_strategy='behavior_units',
        scoped_java_projects={'INTERNET': 'WSBCC_INTERNET', 'IVR': 'WSBCC_IVR', 'XML': 'WSBCC_XML'})
    try:
        import_vault(conn, str(vault), config, progress=lambda _: None)
        report = prepare_scoped_workflow(conn, config, profile)
        assert len(report['operations']) == 10
        assert all(item['status'] == 'prepared' for item in report['operations'].values()), {
            key: value.get('blockers') for key, value in report['operations'].items() if value['status'] != 'prepared'}
        units = report['operations']['INTERNET/GetAccountDetailsOp']['units']
        request = next(unit for unit in units if unit['logical_id'] == 'GetAccountDetailsRQFmt')
        evidence = evidence_catalog(request, request['unit_id'])
        for name in ('CCMandatory', 'CCNullToZero', 'FormatDecoratorHolder', 'AbstractFormatElement', 'DemoXml'):
            assert any(re.search(r'\bclass\s+' + name + r'\b', item['content']) for item in evidence), name
        assert not any('class GetAccountDetailsSP ' in item['content'] for item in evidence)
        assert not any(item['class_name'].endswith(('.CCMandatory', '.CCNullToZero')) for item in request['external_dependencies'])
        from tools.behavior_verification.boundaries import build_boundary_report
        from reachability_bank_trace import trace_bank_request
        boundaries = build_boundary_report(report, tool_jar=boundary_tool)
        assert boundaries['counts'] == dict(total=83, identified=83, incomplete=0)
        assert all(item['reachable_slice']['nodes'] for item in boundaries['boundaries'].values())
        graph = boundaries['boundaries'][request['unit_id']]['reachable_slice']
        assert not any('.format(' in node['signature'] or '.addDecoration(' in node['signature']
                       or '.formatXmlAttributes(' in node['signature'] for node in graph['nodes'])
        trace_bank_request(request, graph, boundary_tool, tmp_path / 'request-trace')
        assert boundaries['checklist_counts']['extracted'] == 83
        assert boundaries['checklist_counts']['incomplete'] == 0
        request_items = boundaries['boundaries'][request['unit_id']]['parser_checklist']['items']
        assert any(item['kind'] == 'literal' and item['properties'].get('value') == 'yyyyMMdd' for item in request_items)
        nil_items = [item for boundary in boundaries['boundaries'].values() if boundary['kind'] == 'response_format'
                     for item in boundary['parser_checklist']['items']
                     if 'NilDecorator' in (item['source_file'] or '')]
        assert any(item['kind'] == 'literal' and item['properties'].get('value') == 'xsi:nil' for item in nil_items)
        assert any(item['kind'] == 'branch' and 'getChannelsToSchemaValidation' in item['properties'].get('condition', '')
                   and 'getApplicationsToExcludeSchemaValidation' in item['properties'].get('condition', '') for item in nil_items)
        assert any(item['kind'] == 'branch' and 'formattedValue == null' in item['properties'].get('condition', '')
                   and 'formattedValue.length() == 0' in item['properties'].get('condition', '') for item in nil_items)
        assert any(item['kind'] == 'exception' and item['detail'] == 'caught' for item in nil_items)
    finally:
        conn.close()
