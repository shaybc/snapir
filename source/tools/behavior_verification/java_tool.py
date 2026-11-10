"""Run the pinned JavaParser tool against supplied evidence, without executing legacy code."""

import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from runtime.java_toolchain import run_java
from tools.behavior_verification.analysis_progress import run_with_progress
from tools.behavior_verification.analysis_xml import read_analysis_xml


def default_tool_path():
    """Locate the separately built converter analysis tool, independent of the workspace."""
    return Path(__file__).resolve().parents[2] / 'behavior-verification-java/target/behavior-verification-1.0.0-jar-with-dependencies.jar'


def analyze_entries(scopes, tool_jar=None, *, collect_checklists=True):
    """Batch isolated source scopes; a missing tool is reported by the caller as incomplete."""
    tool = Path(tool_jar or default_tool_path()).resolve()
    if not tool.is_file():
        raise ValueError('Build the converter analysis tool: mvn -q -f source/behavior-verification-java/pom.xml package')
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    tool_hash = file_digest(tool)
    libraries = {item['path']: item['sha256'] for scope in scopes.values()
                 for project in scope.get('classpath', {}).get('projects', {}).values() for item in project['libraries']}
    def verify_libraries():
        for path, expected in libraries.items():
            if file_digest(path) != expected:
                raise ValueError('Boundary analysis JAR changed after verification: ' + path)
    verify_libraries()
    with tempfile.TemporaryDirectory(prefix='snapir-boundaries-') as temporary:
        folder = Path(temporary)
        manifest = ElementTree.Element('analysis')
        for key, scope in sorted(scopes.items()):
            node = ElementTree.SubElement(manifest, 'scope', id=key)
            context = scope.get('classpath', {})
            if context:
                node.set('project', context['project'])
                for name, project in context['projects'].items():
                    project_node = ElementTree.SubElement(node, 'project', id=name)
                    for identity in project['visible_sources']:
                        ElementTree.SubElement(project_node, 'visible-source', identity=identity)
                    for library in project['libraries']:
                        ElementTree.SubElement(project_node, 'library', **library)
            for source in scope['sources']:
                child = ElementTree.SubElement(node, 'source', identity=source['identity'], hash=source['content_hash'])
                if context:
                    child.set('project', context['source_projects'][source['identity']])
                child.text = source['content']
            for boundary in scope['boundaries']:
                entry = ElementTree.SubElement(node, 'entry', id=boundary.unit_id,
                    implementation=boundary.implementation_class, method=boundary.method_name,
                    returns=boundary.return_contract, kind=boundary.kind, format_scope=boundary.format_scope)
                for parameter in boundary.parameter_contract:
                    ElementTree.SubElement(entry, 'parameter', type=parameter)
                for name in boundary.setup_class_roots:
                    ElementTree.SubElement(entry, 'setup', implementation=name)
                for binding in boundary.setup_bindings:
                    configured = ElementTree.SubElement(entry, 'binding', implementation=binding.implementation_class)
                    for name, value in sorted(binding.attributes.items()):
                        ElementTree.SubElement(configured, 'attribute', name=name, value=value)
                entry.set('reachability', 'true')
                if not collect_checklists:
                    entry.set('checklist', 'false')
        # XML parsers normalize literal CR/CRLF; character references retain exact source text.
        (folder / 'input.xml').write_bytes(ElementTree.tostring(manifest, encoding='utf-8',
            xml_declaration=True).replace(b'\r', b'&#13;'))
        try:
            result = run_with_progress(
                ['java', '-jar', str(tool), str(folder / 'input.xml'), str(folder / 'output.xml')],
                folder / 'progress.log', run_java, output_path=folder / 'output.xml')
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Converter boundary analysis could not finish: ' + str(exc)) from exc
        if result.returncode:
            raise ValueError('Converter boundary analysis failed: ' + result.stderr[-2000:])
        if file_digest(tool) != tool_hash:
            raise ValueError('Converter analysis tool changed during boundary discovery')
        verify_libraries()
        report = read_analysis_xml(folder / 'output.xml')
        if any(scope.get('classpath') for scope in scopes.values()):
            if report.get('classpath_protocol') != 'project-classpath-v1':
                raise ValueError('Boundary analyzer JAR lacks project classpath support; rebuild source/behavior-verification-java/pom.xml')
        if any(boundary.kind != 'configured_step' for scope in scopes.values() for boundary in scope['boundaries']):
            if report.get('format_lifecycle_protocol') != 'format-lifecycle-v1':
                raise ValueError('Boundary analyzer JAR lacks format lifecycle support; rebuild source/behavior-verification-java/pom.xml')
        return report, tool_hash
