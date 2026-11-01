"""Trace disposable original bank-demo sources; this is not an equivalence harness."""

import json
from pathlib import Path
from xml.etree import ElementTree

from runtime.java_toolchain import run_java


def trace_bank_request(unit, graph, tool, directory):
    """Assert real configured request setup and execution methods occur in the static slice."""
    directory.mkdir()
    manifest = ElementTree.Element('scope')
    for source in unit['sources']:
        ElementTree.SubElement(manifest, 'source', identity=source['identity'],
            hash=source['content_hash']).text = source['content']
    ElementTree.ElementTree(manifest).write(directory / 'sources.xml', encoding='utf-8')
    probe = Path(__file__).parent / 'fixtures/ReachabilityTrace.java'
    _run(['javac', '-cp', str(tool), '-d', str(directory), str(probe)])
    import os
    _run(['java', '-cp', os.pathsep.join((str(directory), str(tool))),
          'il.co.dcd.verification.ReachabilityTrace', str(directory / 'sources.xml'), str(directory / 'original')])
    statements = []

    def configured(node):
        name = 'item' + str(len(statements))
        statements.append(f'var {name} = new {node["java_class"]}();')
        attributes = ','.join(f'{json.dumps(k)},{json.dumps(v)}' for k, v in node.get('attributes', {}).items())
        statements.append(f'initialize({name}, new com.ibm.dse.base.Tag(java.util.Map.of({attributes})));')
        for child in node.get('children', []):
            statements.append(f'{name}.addChild({configured(child)});')
        for decorator in node.get('decorators', []):
            decorator_name = configured(decorator)
            statements.append(f'register({name}, {decorator_name});')
        return name

    root = configured(unit['effective_configuration']['children'][0])
    xml = ('<GetAccountDetails><ClientId>123</ClientId><AccountNumber>0000000042</AccountNumber>'
           '<SessionToken>session</SessionToken><FromDate>20240101</FromDate><ToDate>20240102</ToDate>'
           '<MaxTransactions>0005</MaxTransactions></GetAccountDetails>')
    driver = directory / 'BankRequestTrace.java'
    driver.write_text('public class BankRequestTrace { '
        + 'static void initialize(Object value, com.ibm.dse.base.Tag tag) throws Exception { '
        + 'try { value.getClass().getMethod("initializeFrom", com.ibm.dse.base.Tag.class).invoke(value, tag); } '
        + 'catch (NoSuchMethodException absent) {} } '
        + 'static void register(com.ibm.il.dse.cc.format.AbstractFormatElement owner, Object decorator) { '
        + 'if (decorator instanceof com.ibm.dse.base.AttributeXmlFormatDecoratorImpl attribute) owner.addAttributeDecorator(attribute); '
        + 'else owner.addDecorator((com.ibm.dse.base.FormatDecoratorHolder)decorator); } '
        + 'public static void main(String[] args) throws Exception {\n'
        + '\n'.join(statements) + '\nvar context = new com.ibm.dse.base.Context();\n'
        + f'{root}.unformat({json.dumps(xml)}, context);\n'
        + f'try {{ {root}.unformat("<GetAccountDetails/>", context); throw new AssertionError("Mandatory check missing"); }} '
        + 'catch (IllegalArgumentException expected) {}\n} }', encoding='utf-8')
    _run(['javac', '-d', str(directory), *map(str, (directory / 'original').rglob('*.java')), str(driver)])
    output = _run(['java', '-cp', str(directory), 'BankRequestTrace'])
    observed = {line.removeprefix('TRACE:') for line in output.splitlines() if line.startswith('TRACE:')}
    retained = {node['signature'] for node in graph['nodes']}
    assert observed and observed <= retained, sorted(observed - retained)
    assert any('CCPadding.removeDecoration' in method for method in observed)
    assert any('CCMandatory.requireValue' in method for method in observed)
    assert any('CCNullToZero.removeDecoration' in method for method in observed)
    return observed


def _run(command):
    result = run_java(command, capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout
