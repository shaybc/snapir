"""Exercise project-local visibility, precedence and real duplicate-class execution."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import os
import subprocess
import pytest
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.source_discovery_tools.binary_resolution import binary_choice, classpath_for_project
from tools.conversion_tools.scoped_reuse.fingerprints import classpath_fingerprint


def jar(path, value=b'class fixture'):
    with ZipFile(path, 'w') as archive:
        archive.writestr('vendor/Value.class', value)
    return str(path.resolve())


def project(root, name, entries):
    folder = root / name
    folder.mkdir(exist_ok=True)
    (folder / 'src').mkdir(exist_ok=True)
    (folder / '.project').write_text('<projectDescription><name>' + name + '</name></projectDescription>')
    document = ET.Element('classpath')
    ET.SubElement(document, 'classpathentry', kind='src', path='src')
    for entry in entries:
        ET.SubElement(document, 'classpathentry', **entry)
    ET.ElementTree(document).write(folder / '.classpath')
    return folder


@pytest.fixture
def ordered(tmp_path):
    first, second = jar(tmp_path / 'first.jar', b'first'), jar(tmp_path / 'second.jar', b'second')
    project(tmp_path, 'A', [dict(kind='lib', path=first), dict(kind='lib', path=second)])
    project(tmp_path, 'B', [dict(kind='lib', path=second), dict(kind='lib', path=first)])
    return tmp_path, first, second


def test_project_order_selects_different_origins_without_changing_global_inventory(ordered):
    root, first, second = ordered
    index = discover_java_classpath(str(root))
    before = classpath_fingerprint(index)
    for owner, expected in [('A', first), ('B', second)]:
        view = classpath_for_project(index, owner)
        assert view.classes['vendor.Value'] == ['jar:' + expected]
        assert view.binary_resolutions[0]['project'] == owner
        assert view.binary_resolutions[0]['shadowed']
    assert len(index.classes['vendor.Value']) == 2
    assert classpath_fingerprint(index) == before


def test_export_boundaries_and_unrelated_projects(ordered):
    root, first, second = ordered
    project(root, 'B', [dict(kind='lib', path=first), dict(kind='lib', path=second, exported='true')])
    project(root, 'A', [dict(kind='src', path='/B')])
    project(root, 'Unrelated', [dict(kind='lib', path=first)])
    index = discover_java_classpath(str(root))
    assert classpath_for_project(index, 'A').libraries == [second]
    assert classpath_for_project(index, 'B').libraries == [first, second]
    assert classpath_for_project(index, 'A').classes['vendor.Value'] == ['jar:' + second]


def test_containers_expand_in_place_and_can_differ_by_project(ordered):
    root, first, second = ordered
    for name in ('A', 'B'):
        project(root, name, [dict(kind='con', path='runtime'), dict(kind='lib', path=first)])
    index = discover_java_classpath(str(root), containers={'runtime': [first, second]},
        project_containers={'B': {'runtime': [second, first]}})
    assert classpath_for_project(index, 'A').libraries == [first, second]
    assert classpath_for_project(index, 'B').libraries == [second, first]


def test_full_inventory_includes_explicit_owners_outside_default_channel(ordered):
    from models.pipeline_configuration import PipelineConfiguration
    from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath
    root, first, second = ordered
    profile = PipelineConfiguration(source_root=str(root), scoped_java_projects={'INTERNET': 'A', 'IVR': 'B'})
    index = discover_conversion_classpath(str(root), profile=profile)
    assert set(index.project_classpaths) == {'A', 'B'}
    assert classpath_for_project(index, 'B').classes['vendor.Value'] == ['jar:' + second]


def test_directory_discovery_does_not_establish_container_precedence(ordered):
    root, first, second = ordered
    project(root, 'A', [dict(kind='con', path='org.eclipse.jst.server.core.container/com.ibm.ws.ast.st.runtime.runtimeTarget.v85/was.base.v85')])
    index = discover_java_classpath(str(root), variables={'APP_SERVER_PATH': str(root)})
    choice = binary_choice(index, 'vendor.Value', 'A')
    assert choice['status'] == 'unestablished_container_order'
    assert len(choice['locations']) == 2


def test_identical_copies_and_repeated_paths_do_not_create_ambiguity(ordered):
    root, first, second = ordered
    Path(second).write_bytes(Path(first).read_bytes())
    project(root, 'A', [dict(kind='con', path='org.eclipse.jst.server.core.container/com.ibm.ws.ast.st.runtime.runtimeTarget.v85/was.base.v85'),
                        dict(kind='lib', path=first)])
    index = discover_java_classpath(str(root), variables={'APP_SERVER_PATH': str(root)})
    assert len(binary_choice(index, 'vendor.Value', 'A')['locations']) == 1
    assert len(classpath_for_project(index, 'A').libraries) == 2


def test_order_only_change_invalidates_fingerprint_and_missing_stays_missing(ordered):
    root, first, second = ordered
    index = discover_java_classpath(str(root))
    before = classpath_fingerprint(index)
    project(root, 'A', [dict(kind='lib', path=second), dict(kind='lib', path=first)])
    with pytest.raises(ValueError, match='metadata changed'):
        classpath_fingerprint(index)
    fresh = discover_java_classpath(str(root))
    assert classpath_fingerprint(fresh) != before
    assert binary_choice(fresh, 'vendor.Missing', 'A')['status'] == 'missing'


def test_exported_reference_cycle_terminates_and_excludes_test_entries(ordered):
    root, first, second = ordered
    project(root, 'A', [dict(kind='src', path='/B', exported='true'), dict(kind='lib', path=first)])
    folder = project(root, 'B', [dict(kind='src', path='/A', exported='true'), dict(kind='lib', path=second, exported='true')])
    doc = ET.parse(folder / '.classpath')
    node = ET.SubElement(doc.getroot(), 'classpathentry', kind='lib', path=first, exported='true')
    ET.SubElement(ET.SubElement(node, 'attributes'), 'attribute', name='test', value='true')
    doc.write(folder / '.classpath')
    index = discover_java_classpath(str(root))
    assert classpath_for_project(index, 'A').libraries == [second, first]


def test_metadata_supplement_and_serialized_index_keep_order(ordered, monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from models.java_classpath_index import JavaClasspathIndex
    from tools.source_discovery_tools.eclipse_metadata_snapshot import publish_supplement
    root, first, second = ordered
    index = discover_java_classpath(str(root))
    saved = JavaClasspathIndex.model_validate_json(index.model_dump_json())
    assert classpath_for_project(saved, 'B').libraries == [second, first]
    monkeypatch.setattr('tools.composer_mapper_tools.mapped_scope.current_mapped',
        lambda workspace: SimpleNamespace(config=SimpleNamespace(db_path=str(tmp_path / 'state/run.db'))))
    publish_supplement(root, saved)
    data = json.loads((tmp_path / 'state/eclipse-metadata.json').read_text())
    assert data['project_classpaths']['B']['entries'][1]['path'] == second
    assert any(item['project'] == 'B' and item['locations'] == ['jar:' + second] for item in data['binary_resolutions'])


def test_original_comparison_uses_existing_sequence_for_unspecified_container_order(ordered, monkeypatch):
    from types import SimpleNamespace
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.behavior_conversion.original_classpath import original_classpath
    root, first, second = ordered
    monkeypatch.setattr('tools.behavior_verification.boundary_contracts.boundary_contract',
        lambda unit: SimpleNamespace(implementation_class='example.Main'))
    profile = PipelineConfiguration(source_root=str(root), scoped_java_project='B')
    assert original_classpath(profile, {}) == [second, first]
    project(root, 'B', [dict(kind='con', path='org.eclipse.jst.server.core.container/com.ibm.ws.ast.st.runtime.runtimeTarget.v85/was.base.v85')])
    profile.eclipse_classpath_variables = {'APP_SERVER_PATH': str(root)}
    resolved = original_classpath(profile, {})
    index = discover_java_classpath(str(root), profile.classpath_jars, profile.eclipse_classpath_variables)
    expected = [entry.path for entry in index.project_classpaths['B'].entries if entry.kind == 'library']
    assert resolved == expected
    assert resolved


def test_old_flat_index_remains_conservative_and_explicit_empty_container_is_valid(tmp_path):
    from models.java_classpath_index import JavaClasspathIndex
    old = JavaClasspathIndex(classes={'vendor.Value': ['jar:a', 'jar:b']})
    assert classpath_for_project(old, 'A').classes['vendor.Value'] == ['jar:a', 'jar:b']
    project(tmp_path, 'A', [dict(kind='con', path='empty')])
    current = discover_java_classpath(str(tmp_path), containers={'empty': []})
    assert not current.issues
    assert classpath_for_project(current, 'A').libraries == []


def test_compiler_and_runtime_follow_selected_project_order(ordered, tmp_path):
    from runtime.java_toolchain import java_environment
    root, first, second = ordered
    environment = java_environment(25, None)
    java_bin = Path(environment['JAVA_HOME']) / 'bin'
    for target, value in [(first, 'first'), (second, 'second')]:
        folder = tmp_path / value
        source = folder / 'vendor/Value.java'
        source.parent.mkdir(parents=True)
        source.write_text('package vendor; public class Value { public static String get(){return "' + value + '";} }')
        result = subprocess.run([str(java_bin / 'javac.exe'), '-d', str(folder), str(source)], env=environment, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
        with ZipFile(target, 'w') as archive:
            archive.write(folder / 'vendor/Value.class', 'vendor/Value.class')
    index = discover_java_classpath(str(root))
    main = tmp_path / 'Caller.java'
    main.write_text('public class Caller { public static void main(String[] args){System.out.print(vendor.Value.get());} }')
    for owner, expected in [('A', 'first'), ('B', 'second')]:
        view = classpath_for_project(index, owner)
        cp = os.pathsep.join(view.libraries)
        result = subprocess.run([str(java_bin / 'javac.exe'), '-cp', cp, str(main)], env=environment, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(java_bin / 'java.exe'), '-cp', str(tmp_path) + os.pathsep + cp, 'Caller'], env=environment, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0 and result.stdout == expected
