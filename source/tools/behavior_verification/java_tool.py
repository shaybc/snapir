"""Run the pinned JavaParser tool against supplied evidence, without executing legacy code."""

import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from runtime.java_toolchain import run_java


def default_tool_path():
    """Locate the separately built converter analysis tool, independent of the workspace."""
    return Path(__file__).resolve().parents[2] / 'behavior-verification-java/target/behavior-verification-1.0.0-jar-with-dependencies.jar'


def analyze_entries(scopes, tool_jar=None):
    """Batch isolated source scopes; a missing tool is reported by the caller as incomplete."""
    tool = Path(tool_jar or default_tool_path()).resolve()
    if not tool.is_file():
        raise ValueError('Build the converter analysis tool: mvn -q -f source/behavior-verification-java/pom.xml package')
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    tool_hash = file_digest(tool)
    with tempfile.TemporaryDirectory(prefix='snapir-boundaries-') as temporary:
        folder = Path(temporary)
        manifest = ElementTree.Element('analysis')
        for key, scope in sorted(scopes.items()):
            node = ElementTree.SubElement(manifest, 'scope', id=key)
            for source in scope['sources']:
                child = ElementTree.SubElement(node, 'source', identity=source['identity'], hash=source['content_hash'])
                child.text = source['content']
            for boundary in scope['boundaries']:
                entry = ElementTree.SubElement(node, 'entry', id=boundary.unit_id,
                    implementation=boundary.implementation_class, method=boundary.method_name,
                    returns=boundary.return_contract, kind=boundary.kind)
                for parameter in boundary.parameter_contract:
                    ElementTree.SubElement(entry, 'parameter', type=parameter)
                for name in boundary.setup_class_roots:
                    ElementTree.SubElement(entry, 'setup', implementation=name)
                for binding in boundary.setup_bindings:
                    configured = ElementTree.SubElement(entry, 'binding', implementation=binding.implementation_class)
                    for name, value in sorted(binding.attributes.items()):
                        ElementTree.SubElement(configured, 'attribute', name=name, value=value)
                entry.set('reachability', 'true')
        ElementTree.ElementTree(manifest).write(folder / 'input.xml', encoding='utf-8', xml_declaration=True)
        try:
            result = run_java(['java', '-jar', str(tool), str(folder / 'input.xml'), str(folder / 'output.xml')],
                              capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Converter boundary analysis could not finish: ' + str(exc)) from exc
        if result.returncode:
            raise ValueError('Converter boundary analysis failed: ' + result.stderr[-2000:])
        if file_digest(tool) != tool_hash:
            raise ValueError('Converter analysis tool changed during boundary discovery')
        report = ElementTree.parse(folder / 'output.xml').getroot()
        return report, tool_hash
