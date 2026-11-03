"""Run source-only JavaParser checks in the pinned analysis tool."""
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.boundary_protocol import value_element, read_value, configuration_element
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest


def inspect_static_sources(unit, boundary, files, answers, policy, tool=None):
    """Inspect current candidate tokens and original dead branches without running either side."""
    tool = Path(tool or default_tool_path()).resolve()
    if not tool.is_file():
        raise ValueError('Build the converter Java analysis tool before static verification')
    fingerprint = file_digest(tool)
    root = ET.Element('static_checks')
    native = ET.SubElement(root, 'native')
    for path, content in sorted(files.items()):
        if not path.startswith('src/main/java/'):
            continue
        node = ET.SubElement(native, 'file', path=path)
        ET.SubElement(node, 'source').text = content
        for answer in answers.responses:
            for index, location in enumerate(answer.locations):
                if location.path == path:
                    query = ET.SubElement(node, 'location', id=answer.checklist_id + ':' + str(index))
                    query.append(value_element(location.excerpt, 'excerpt'))
    legacy = ET.SubElement(root, 'legacy', kind=boundary.kind)
    if boundary.kind in {'request_unformat','response_format'}:
        definitions={item['definition_id']:item for item in unit.get('referenced_definitions',[])}
        legacy.append(configuration_element(unit['effective_configuration'],definitions))
    for source in unit['sources']:
        ET.SubElement(legacy, 'source', identity=source['identity'], hash=source['content_hash']).text = source['content']
    for edge in boundary.reachable_slice.edges:
        fields = ('id', 'kind', 'from_id', 'declared_target', 'uncertain', 'unbounded', 'start_line', 'start_column', 'end_line', 'end_column')
        node = ET.SubElement(legacy, 'edge', **{key: str(getattr(edge, key)).lower() if isinstance(getattr(edge, key), bool)
                                             else str(getattr(edge, key)) for key in fields if getattr(edge, key) is not None})
        for identity in edge.candidates:
            ET.SubElement(node, 'candidate', id=identity)
    for kind, identities in boundary.reachable_slice.roots.items():
        for identity in identities:
            ET.SubElement(legacy, 'root', kind=kind, id=identity)
    for binding in boundary.setup_bindings:
        node = ET.SubElement(legacy, 'binding', implementation=binding.implementation_class)
        for key, value in sorted(binding.attributes.items()):
            ET.SubElement(node, 'attribute', name=key, value=value)
    for contract in policy.tag_contracts:
        ET.SubElement(legacy, 'tag_contract', **{'class': contract.tag_class, 'hash': contract.source_hash,
                                              'getter': contract.getter, 'id': contract.contract_id})
    for item in boundary.parser_checklist.items if boundary.parser_checklist is not None else ():
        fields = ('id', 'kind', 'detail', 'code_node_id', 'syntax_type', 'source_identity', 'source_hash',
                  'start_line', 'start_column', 'end_line', 'end_column')
        ET.SubElement(legacy, 'item', **{key: str(getattr(item, key)) for key in fields})
    with tempfile.TemporaryDirectory(prefix='snapir-static-checks-') as folder:
        input_path, output_path = Path(folder) / 'input.xml', Path(folder) / 'output.xml'
        input_path.write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True).replace(b'\r', b'&#13;'))
        result = run_java(['java', '-cp', str(tool), 'il.co.dcd.verification.StaticCheckAnalysis',
                           str(input_path), str(output_path)], capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise ValueError('Static Java analysis failed: ' + result.stderr[-2000:])
        if file_digest(tool) != fingerprint:
            raise ValueError('Static analysis tool changed during verification')
        return read_value(ET.parse(output_path).getroot()), fingerprint
