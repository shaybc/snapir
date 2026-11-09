"""Verify binary class discovery and conservative import classification."""

from zipfile import ZipFile

from models.java_classpath_index import JavaClasspathIndex
from models.java_source_index import JavaSourceIndex
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.source_discovery_tools.dependencies import classify_java_imports


def jar_file(path, *classes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name in classes:
            archive.writestr(name.replace(".", "/") + ".class", b"fixture")
    return str(path)


def test_explicit_jar_provides_class(tmp_path):
    jar = jar_file(tmp_path / "library.jar", "org.example.Client")
    index = discover_java_classpath(str(tmp_path), [jar])
    assert index.classes["org.example.Client"] == ["jar:" + jar]


def test_eclipse_relative_library_is_discovered(tmp_path):
    jar = jar_file(tmp_path / "project/lib/client.jar", "org.example.Client")
    (tmp_path / "project/.classpath").write_text('<classpath><classpathentry kind="lib" path="lib/client.jar"/></classpath>')
    assert jar in discover_java_classpath(str(tmp_path)).libraries


def test_eclipse_workspace_library_uses_workspace_not_drive_root(tmp_path):
    jar = jar_file(tmp_path / 'War/WebContent/WEB-INF/lib/client.jar', 'org.example.Client')
    project = tmp_path / 'Caller'
    project.mkdir()
    (project / '.classpath').write_text('<classpath><classpathentry kind="lib" path="/War/WebContent/WEB-INF/lib/client.jar"/></classpath>')
    index = discover_java_classpath(str(tmp_path))
    assert jar in index.libraries
    assert not any('Missing classpath library' in issue for issue in index.issues)


def test_eclipse_declared_project_name_and_explicit_absolute_library(tmp_path):
    jar = jar_file(tmp_path / 'different-folder/lib/client.jar', 'org.example.Client')
    (tmp_path / 'different-folder/.project').write_text('<projectDescription><name>Shared</name></projectDescription>')
    caller = tmp_path / 'Caller'
    caller.mkdir()
    (caller / '.classpath').write_text('<classpath><classpathentry kind="lib" path="/Shared/lib/client.jar"/></classpath>')
    index = discover_java_classpath(str(tmp_path), [jar])
    assert index.libraries.count(jar) == 1


def test_explicit_container_binding_and_variable_are_resolved(tmp_path):
    jar = jar_file(tmp_path / 'runtime/lib/client.jar', 'org.example.Client')
    project = tmp_path / 'Project'
    project.mkdir()
    (project / '.classpath').write_text('<classpath><classpathentry kind="con" path="vendor.RUNTIME"/>'
                                      '<classpathentry kind="var" path="RUNTIME/lib/client.jar"/></classpath>')
    index = discover_java_classpath(str(tmp_path), variables={'RUNTIME': str(tmp_path / 'runtime')},
                                    containers={'vendor.RUNTIME': [jar]})
    assert jar in index.libraries and not index.issues


def test_relevant_container_and_missing_library_keep_actionable_provenance(tmp_path):
    (tmp_path / '.classpath').write_text('<classpath><classpathentry kind="con" path="vendor.RUNTIME"/>'
                                       '<classpathentry kind="lib" path="lib/missing.jar"/></classpath>')
    index = discover_java_classpath(str(tmp_path))
    assert {issue.kind for issue in index.issue_details} == {'container', 'library'}
    assert all(issue.project == str(tmp_path) for issue in index.issue_details)
    assert any(issue.reference == 'vendor.RUNTIME' for issue in index.issue_details)


def test_selected_classpath_ignores_unrelated_broken_project(tmp_path):
    jar = jar_file(tmp_path / 'Selected/lib/client.jar', 'org.example.Client')
    (tmp_path / 'Selected/.classpath').write_text('<classpath><classpathentry kind="lib" path="lib/client.jar"/></classpath>')
    unrelated = tmp_path / 'Other'
    unrelated.mkdir()
    (unrelated / '.classpath').write_text('<classpath><classpathentry kind="var" path="MISSING/library.jar"/></classpath>')
    index = discover_java_classpath(str(tmp_path), visible_source_roots=[str(tmp_path / 'Selected/src')])
    assert jar in index.libraries
    assert not any('MISSING' in issue for issue in index.issues)


def test_unresolved_variable_is_reported(tmp_path):
    (tmp_path / ".classpath").write_text('<classpath><classpathentry kind="var" path="LIBS/client.jar"/></classpath>')
    assert any("Unresolved Eclipse variable" in issue for issue in discover_java_classpath(str(tmp_path)).issues)


def test_missing_and_invalid_libraries_are_reported(tmp_path):
    broken = tmp_path / "broken.jar"
    broken.write_text("invalid")
    index = discover_java_classpath(str(tmp_path), [str(broken), str(tmp_path / "missing.jar")])
    assert any("Invalid classpath archive" in issue for issue in index.issues)
    assert any("Missing classpath library" in issue for issue in index.issues)


def test_classification_detects_conflicts_framework_and_missing(tmp_path):
    source = tmp_path / "Example.java"
    source.write_text("import org.example.Client;\nimport com.ibm.Framework;\nimport org.missing.Type;\nimport org.example.*;")
    sources = JavaSourceIndex(workspace_root=str(tmp_path))
    binary = JavaClasspathIndex(classes={"org.example.Client": ["jar:a", "jar:b"], "com.ibm.Framework": ["jar:ibm"]})
    results = classify_java_imports(str(source), sources, binary)
    assert [item["kind"] for item in results] == ["ambiguous", "replacement_required", "missing", "needs_review"]


def test_static_import_resolves_owning_type(tmp_path):
    source = tmp_path / "Example.java"
    source.write_text("import static org.example.Client.create;")
    binary = JavaClasspathIndex(classes={"org.example.Client": ["jar:a"]})
    assert classify_java_imports(str(source), JavaSourceIndex(workspace_root=str(tmp_path)), binary)[0]["kind"] == "library"
