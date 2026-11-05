"""Exercise production source discovery and ambiguous class resolution."""

import pytest

from tools.source_discovery_tools import discover_java_sources, resolve_indexed_source
from tools.source_discovery_tools.resolver import AmbiguousJavaSourceError
from tools.java_analysis_tools.java_source_reader import resolve_source_path


def java_file(root, relative="com/bank/Example.java"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("package com.bank; public class Example {}", encoding="utf-8")
    return str(path.resolve())


def test_discovers_multiple_conventional_projects(tmp_path):
    first = java_file(tmp_path / "internet/src")
    second = java_file(tmp_path / "ivr/src", "com/bank/Other.java")
    index = discover_java_sources(str(tmp_path))
    assert resolve_indexed_source(index, "com.bank.Example") == first
    assert resolve_source_path(str(tmp_path), "com.bank.Other") == second
    assert index.issues == []


def test_eclipse_metadata_defines_custom_source_root(tmp_path):
    project = tmp_path / "project"
    source = java_file(project / "business-code")
    (project / ".project").write_text("<projectDescription><name>Bank</name></projectDescription>")
    (project / ".classpath").write_text('<classpath><classpathentry kind="src" path="business-code"/></classpath>')
    index = discover_java_sources(str(tmp_path))
    assert resolve_indexed_source(index, "com.bank.Example", "Bank") == source
    assert index.issues == []


def test_malformed_metadata_does_not_fall_back(tmp_path):
    project = tmp_path / "project"
    java_file(project / "src")
    (project / ".classpath").write_text("<broken")
    index = discover_java_sources(str(tmp_path))
    assert index.issues
    assert resolve_indexed_source(index, "com.bank.Example") is None


def test_duplicate_classes_require_explicit_ownership(tmp_path):
    first = java_file(tmp_path / "internet/src")
    java_file(tmp_path / "ivr/src")
    index = discover_java_sources(str(tmp_path))
    with pytest.raises(AmbiguousJavaSourceError):
        resolve_indexed_source(index, "com.bank.Example")
    assert resolve_indexed_source(index, "com.bank.Example", "internet") == first


def test_maven_layout_excludes_test_sources(tmp_path):
    source = java_file(tmp_path / "project/src/main/java")
    java_file(tmp_path / "project/src/test/java")
    index = discover_java_sources(str(tmp_path))
    assert resolve_indexed_source(index, "com.bank.Example") == source


def test_missing_metadata_source_root_is_reported(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".classpath").write_text('<classpath><classpathentry kind="src" path="missing"/></classpath>')
    assert "Missing source root" in discover_java_sources(str(tmp_path)).issues[0]


def test_project_reference_resolves_other_project(tmp_path):
    owner = tmp_path / "owner"
    owner.mkdir()
    (owner / ".classpath").write_text('<classpath><classpathentry kind="src" path="/Shared"/></classpath>')
    shared = tmp_path / "shared"
    source = java_file(shared / "src")
    (shared / ".project").write_text("<projectDescription><name>Shared</name></projectDescription>")
    index = discover_java_sources(str(tmp_path))
    assert resolve_indexed_source(index, "com.bank.Example", "owner") == source


@pytest.mark.parametrize("content", [
    "", " \t\n", "\ufeff \n",
    "// package com.bank;\n// public class Unused {}",
    "/* package com.bank;\n public class Unused {} */",
    "/** Retired source. */\n // Nothing remains\n /* End */",
])
@pytest.mark.parametrize("relative", ["Unused.java", "com/bank/Unused.java"])
def test_empty_and_comment_only_sources_are_not_indexed(tmp_path, content, relative):
    root = tmp_path / "project/src"
    source = java_file(root)
    unused = root / relative
    unused.parent.mkdir(parents=True, exist_ok=True)
    unused.write_text(content, encoding="utf-8")
    index = discover_java_sources(str(tmp_path))
    assert index.classes == {"com.bank.Example": [source]}
    assert index.class_projects == {source: "project"}
    assert index.issues == []


def test_real_source_without_package_still_reports_mismatched_root(tmp_path):
    path = tmp_path / "project/src/com/bank/Unused.java"
    path.parent.mkdir(parents=True)
    path.write_text("// No package declaration\npublic class Unused {}", encoding="utf-8")
    index = discover_java_sources(str(tmp_path))
    assert index.classes == {}
    assert index.issues == [f"Package does not match source root: {path}"]


def test_default_package_source_is_still_indexed(tmp_path):
    path = tmp_path / "project/src/Example.java"
    path.parent.mkdir(parents=True)
    path.write_text("// Default package\npublic class Example {}", encoding="utf-8")
    index = discover_java_sources(str(tmp_path))
    assert index.classes == {"Example": [str(path.resolve())]}
    assert index.issues == []
