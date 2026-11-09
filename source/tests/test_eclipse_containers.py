"""Exercise exported Eclipse container metadata without an installed Eclipse runtime."""

from types import SimpleNamespace
from pathlib import Path
import json
import pytest

from models.java_source_index import JavaSourceIndex
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.source_discovery_tools.eclipse_containers import container_libraries
from tools.source_discovery_tools.eclipse_project_containers import MODULE_CONTAINER, WEB_CONTAINER
from tools.conversion_tools.scoped_reuse.fingerprints import classpath_fingerprint
from tools.source_discovery_tools.eclipse_metadata_snapshot import read_metadata, publish_supplement
from tools.source_discovery_tools.classpath_scope import with_component_projects
from tests.test_java_classpath import jar_file

RUNTIME = 'org.eclipse.jst.server.core.container/com.ibm.ws.ast.st.runtime.runtimeTarget.v85/was.base.v85'
JUNIT = 'org.eclipse.jdt.junit.JUNIT_CONTAINER/4'


def project(root, name, containers, component=None, extra=''):
    folder = root / name
    (folder / 'src').mkdir(parents=True)
    (folder / '.project').write_text('<projectDescription><name>' + name + '</name></projectDescription>')
    (folder / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/>' + extra + ''.join(
        '<classpathentry kind="con" path="' + container + '"/>' for container in containers) + '</classpath>')
    if component is not None:
        (folder / '.settings').mkdir()
        (folder / '.settings/org.eclipse.wst.common.component').write_text(
            '<project-modules><wb-module deploy-name="' + name + '">' + component + '</wb-module></project-modules>')
    return folder


def test_exact_websphere_identifier_and_explicit_override(tmp_path):
    jar = jar_file(tmp_path / 'runtime/runtimes/client.jar', 'org.example.Client')
    variables = {'APP_SERVER_PATH': str(tmp_path / 'runtime')}
    assert container_libraries(RUNTIME, variables, {}) == [Path(jar)]
    assert container_libraries(RUNTIME.replace('.st.runtime.runtimeTarget', '.st.runtimeTarget'), variables, {}) == [Path(jar)]
    assert container_libraries(RUNTIME, variables, {RUNTIME: ['override.jar']}) == [Path('override.jar')]
    assert container_libraries('vendor.unrelated', variables, {}) is None
    assert container_libraries(RUNTIME, {}, {}) is None


def test_empty_module_is_resolved_and_metadata_changes_freshness(tmp_path):
    folder = project(tmp_path, 'Common', [MODULE_CONTAINER], '<wb-resource deploy-path="/" source-path="/src"/>')
    index = discover_java_classpath(str(tmp_path))
    assert not index.issues
    assert index.project_references == {'Common': []}
    assert index.container_resolutions[0]['method'] == 'component_metadata'
    baseline = classpath_fingerprint(index)
    component = folder / '.settings/org.eclipse.wst.common.component'
    component.write_text(component.read_text() + '\n')
    with pytest.raises(ValueError, match='changed after resolution'):
        classpath_fingerprint(index)
    assert classpath_fingerprint(discover_java_classpath(str(tmp_path))) != baseline
    component.unlink()
    assert discover_java_classpath(str(tmp_path)).issues


def test_web_resources_and_cyclic_modules_do_not_expand_conversion_selection(tmp_path):
    common = project(tmp_path, 'Common', [MODULE_CONTAINER], '<dependent-module handle="module:/resource/War/War"/>')
    war = project(tmp_path, 'War', [MODULE_CONTAINER, WEB_CONTAINER],
        '<wb-resource deploy-path="/" source-path="/website"/>'
        '<dependent-module handle="module:/resource/Common/Common"/>')
    jar = jar_file(war / 'website/WEB-INF/lib/client.jar', 'example.Client')
    index = discover_java_classpath(str(tmp_path), visible_source_roots=[str(war / 'src')])
    assert not index.issues
    assert index.libraries == [jar]
    assert index.project_references == {'War': ['Common']}
    assert all(record['project'] == str(war) for record in index.container_resolutions)
    sources = JavaSourceIndex(workspace_root=str(tmp_path), project_references={'War': []})
    augmented = with_component_projects(sources, index)
    assert augmented.project_references == {'War': ['Common']}
    assert sources.project_references == {'War': []}


@pytest.mark.parametrize('component,expected', [
    (None, 'Missing Eclipse component'),
    ('<dependent-module handle="module:/resource/Absent/Absent"/>', 'Missing Eclipse module project'),
    ('<dependent-module handle="module:/classpath/lib/foo.jar"/>', 'Unsupported Eclipse module handle'),
    ('<wb-resource deploy-path="/" source-path="/../../outside"/>', 'escapes project'),
])
def test_invalid_component_keeps_blocker(tmp_path, component, expected):
    project(tmp_path, 'Common', [MODULE_CONTAINER], component)
    index = discover_java_classpath(str(tmp_path))
    assert any(expected in message for message in index.issues)
    assert all(issue.reference == MODULE_CONTAINER for issue in index.issue_details)


def test_junit_is_excluded_only_with_test_scope_and_no_production_requirement(tmp_path):
    folder = project(tmp_path, 'Xml', [JUNIT], extra='<classpathentry kind="src" path="test"/>')
    (folder / 'src/Main.java').write_text('public class Main {}')
    (folder / 'test').mkdir()
    index = discover_java_classpath(str(tmp_path))
    assert not index.issues
    assert index.container_resolutions[0]['scope'] == 'test'
    (folder / 'src/Main.java').write_text('import org.junit.Test; public class Main {}')
    assert any(JUNIT in message for message in discover_java_classpath(str(tmp_path)).issues)


def test_junit_without_test_evidence_requires_binding(tmp_path):
    project(tmp_path, 'Xml', [JUNIT])
    assert any(JUNIT in message for message in discover_java_classpath(str(tmp_path)).issues)


def test_explicit_binding_overrides_missing_component_and_duplicate_origins_remain(tmp_path):
    folder = project(tmp_path, 'War', [WEB_CONTAINER])
    first = jar_file(folder / 'lib/one.jar', 'example.Same')
    second = jar_file(folder / 'lib/two.jar', 'example.Same')
    index = discover_java_classpath(str(tmp_path), containers={WEB_CONTAINER: [first, second]})
    assert not index.issues
    assert len(index.classes['example.Same']) == 2
    assert index.container_resolutions[0]['method'] == 'explicit_binding'


def test_direct_web_library_resource_is_supported(tmp_path):
    folder = project(tmp_path, 'War', [WEB_CONTAINER], '<wb-resource deploy-path="/WEB-INF/lib" source-path="/libraries"/>')
    jar = jar_file(folder / 'libraries/client.jar', 'example.Client')
    assert discover_java_classpath(str(tmp_path)).libraries == [jar]


def test_missing_web_resource_and_malformed_metadata_block(tmp_path):
    folder = project(tmp_path, 'War', [WEB_CONTAINER], '<wb-resource deploy-path="/" source-path="/absent"/>')
    assert any('Missing Eclipse web resource' in message for message in discover_java_classpath(str(tmp_path)).issues)
    (folder / '.settings/org.eclipse.wst.common.component').write_text('<broken')
    assert discover_java_classpath(str(tmp_path)).issues


def test_project_without_declared_name_keeps_folder_identity(tmp_path):
    folder = project(tmp_path, 'Common', [MODULE_CONTAINER], '')
    (folder / '.project').write_text('<projectDescription/>')
    index = discover_java_classpath(str(tmp_path))
    assert not index.issues
    assert index.project_references == {'Common': []}


def test_duplicate_module_project_name_is_not_selected_arbitrarily(tmp_path):
    project(tmp_path, 'Common', [], '')
    other = project(tmp_path, 'Other', [], '')
    (other / '.project').write_text('<projectDescription><name>Common</name></projectDescription>')
    project(tmp_path, 'War', [MODULE_CONTAINER], '<dependent-module handle="module:/resource/Common/Common"/>')
    assert any('Ambiguous Eclipse module project' in message for message in discover_java_classpath(str(tmp_path)).issues)


def test_metadata_budget_entities_and_missing_revision(tmp_path):
    path = tmp_path / 'component'
    evidence = {}
    assert read_metadata(path, tmp_path, evidence) is None
    assert evidence == {str(path): None}
    path.write_bytes(b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='1 MiB'):
        read_metadata(path, tmp_path, evidence)
    path.write_text('<!DOCTYPE x><project-modules/>')
    with pytest.raises(ValueError, match='entity declaration'):
        read_metadata(path, tmp_path, evidence)


def test_metadata_cannot_change_between_two_container_reads(tmp_path):
    path = tmp_path / 'component'
    path.write_text('<project-modules/>')
    evidence = {}
    read_metadata(path, tmp_path, evidence)
    assert read_metadata(path, tmp_path, evidence).tag == 'project-modules'
    path.write_text('<project-modules> </project-modules>')
    with pytest.raises(ValueError, match='changed during resolution'):
        read_metadata(path, tmp_path, evidence)
    path.unlink()
    with pytest.raises(ValueError, match='changed during resolution'):
        read_metadata(path, tmp_path, evidence)


def test_supplement_is_run_local_and_does_not_modify_map(tmp_path, monkeypatch):
    from tools.composer_mapper_tools import mapped_scope
    from models.java_classpath_index import JavaClasspathIndex
    directory = tmp_path / 'run/state'
    directory.mkdir(parents=True)
    analysis = tmp_path / 'analysis.sqlite'
    analysis.write_bytes(b'original map')
    mapped = SimpleNamespace(config=SimpleNamespace(db_path=str(directory / 'migration.db')))
    monkeypatch.setattr(mapped_scope, 'current_mapped', lambda *_: mapped)
    index = JavaClasspathIndex(metadata_fingerprints={str(tmp_path / 'component'): None})
    publish_supplement(tmp_path, index)
    saved = json.loads((directory / 'eclipse-metadata.json').read_text())
    assert saved['files'] == index.metadata_fingerprints
    assert analysis.read_bytes() == b'original map'
