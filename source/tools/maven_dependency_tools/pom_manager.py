"""Merge verified dependency proposals into a single canonical project POM."""

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from xml.etree import ElementTree

from tools.maven_dependency_tools.policy import validate_dependency_policy
from models.maven_dependency import MavenDependency
from constants import JAVA_VERSION


def initialize_managed_pom(pom_path: str, group_id: str, artifact_id: str,
                           version: str = "1.0.0", java_version: int | None = None) -> None:
    """Create a minimal canonical POM once; never overwrite an existing build."""
    if java_version is None:
        from runtime.java_toolchain import java_version as selected_version
        java_version = int(selected_version())
    MavenDependency(group_id=group_id, artifact_id=artifact_id, version=version, reason="Project identity")
    if java_version < 8:
        raise ValueError("Java version must be at least 8")
    path = Path(pom_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with project_lock(path):
        if path.exists():
            validate_java_target(path.read_text(encoding="utf-8"), java_version)
            return
        root = ElementTree.Element("project", xmlns="http://maven.apache.org/POM/4.0.0")
        for name, value in (("modelVersion", "4.0.0"), ("groupId", group_id),
                            ("artifactId", artifact_id), ("version", version)):
            ElementTree.SubElement(root, name).text = value
        properties = ElementTree.SubElement(root, "properties")
        for name, value in (("maven.compiler.release", str(java_version)), ("maven.compiler.source", str(java_version)),
                            ("maven.compiler.target", str(java_version)), ("project.build.sourceEncoding", "UTF-8")):
            ElementTree.SubElement(properties, name).text = value
        plugins = ElementTree.SubElement(ElementTree.SubElement(root, "build"), "plugins")
        compiler = ElementTree.SubElement(plugins, "plugin")
        for name, value in (("groupId", "org.apache.maven.plugins"),
                            ("artifactId", "maven-compiler-plugin"), ("version", "3.14.1")):
            ElementTree.SubElement(compiler, name).text = value
        enforcer = ElementTree.SubElement(plugins, "plugin")
        for name, value in (("groupId", "org.apache.maven.plugins"),
                            ("artifactId", "maven-enforcer-plugin"), ("version", "3.6.2")):
            ElementTree.SubElement(enforcer, name).text = value
        execution = ElementTree.SubElement(ElementTree.SubElement(enforcer, "executions"), "execution")
        ElementTree.SubElement(ElementTree.SubElement(execution, "goals"), "goal").text = "enforce"
        rules = ElementTree.SubElement(ElementTree.SubElement(execution, "configuration"), "rules")
        requirement = ElementTree.SubElement(rules, "requireJavaVersion")
        ElementTree.SubElement(requirement, "version").text = f"[{java_version},{java_version + 1})"
        path.write_bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))


def validate_java_target(pom: str, java_version: int | None = None) -> None:
    """Reject missing release and conflicting Java targets in generated Maven builds."""
    if java_version is None:
        from runtime.java_toolchain import java_version as selected_version
        java_version = int(selected_version())
    root = ElementTree.fromstring(pom)
    properties = root.find("{*}properties")
    values = {} if properties is None else {node.tag.split("}")[-1]: (node.text or "").strip() for node in properties}
    expected = str(java_version)
    if values.get("maven.compiler.release") != expected:
        raise ValueError(f"Generated POM requires maven.compiler.release={expected}")
    targets = [node for container in root.findall(".//{*}properties") for node in container if node.tag.split("}")[-1] in
        {"java.version", "maven.compiler.source", "maven.compiler.target", "maven.compiler.release",
         "maven.compiler.testSource", "maven.compiler.testTarget", "maven.compiler.testRelease"}]
    for plugin in root.findall(".//{*}plugin"):
        if plugin.findtext("{*}artifactId") == "maven-compiler-plugin":
            targets.extend(node for node in plugin.iter() if node.tag.split("}")[-1] in
                           {"source", "target", "release", "testSource", "testTarget", "testRelease"})
    for node in targets:
        name = node.tag.split("}")[-1]
        value = (node.text or "").strip()
        value = values.get(value[2:-1], value) if value.startswith("${") and value.endswith("}") else value
        if value != expected:
            raise ValueError(f"Generated POM {name} must target Java {expected}, found {value}")


@contextmanager
def project_lock(pom_path: Path, timeout_seconds: float = 10):
    """Serialize cooperating processes; never silently remove an existing lock."""
    lock = pom_path.with_suffix(".xml.lock")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("Managed POM is locked by another writer")
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.unlink()


def merge_dependencies(pom_path: str, proposals, verifier, *, allowed_ibm_artifacts=(), task_id="") -> str:
    """Verify and atomically merge dependencies; return the resulting content hash.

    The POM must already exist. Conflicting versions/scopes abort the whole update.
    The verifier is supplied by trusted runtime configuration, never model output.
    """
    path = Path(pom_path).resolve()
    for dependency in proposals:
        validate_dependency_policy(dependency, allowed_ibm_artifacts)
        verifier(dependency)
    with project_lock(path):
        tree = ElementTree.parse(path, parser=ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True)))
        root = tree.getroot()
        ns = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
        if root.tag != ns + "project":
            raise ValueError("Managed POM must be a Maven project")
        if root.findall(".//" + ns + "systemPath"):
            raise ValueError("Managed POM cannot contain local JAR references")
        container = root.find(ns + "dependencies")
        if container is None:
            container = ElementTree.SubElement(root, ns + "dependencies")
        existing = {}
        for node in container.findall(ns + "dependency"):
            key = (node.findtext(ns + "groupId"), node.findtext(ns + "artifactId"))
            if key in existing:
                raise ValueError("Managed POM contains duplicate dependencies")
            existing[key] = (node.findtext(ns + "version"), node.findtext(ns + "scope", "compile"))
            validate_dependency_policy(MavenDependency(
                group_id=key[0], artifact_id=key[1], version=existing[key][0],
                scope=existing[key][1], reason="Existing managed POM dependency",
            ), allowed_ibm_artifacts)
        for dependency in proposals:
            key = (dependency.group_id, dependency.artifact_id)
            value = (dependency.version, dependency.scope)
            if key in existing and existing[key] != value:
                raise ValueError(f"Dependency version/scope conflict: {dependency.group_id}:{dependency.artifact_id}")
            if key not in existing:
                node = ElementTree.SubElement(container, ns + "dependency")
                for name, text in (("groupId", dependency.group_id), ("artifactId", dependency.artifact_id),
                                   ("version", dependency.version), ("scope", dependency.scope)):
                    ElementTree.SubElement(node, ns + name).text = text
                existing[key] = value
        if ns:
            ElementTree.register_namespace("", ns[1:-1])
        content = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
        digest = hashlib.sha256(content).hexdigest()
        audit = path.with_name("dependency_audit.jsonl")
        # Write intent before publishing the POM; its hash identifies whether it committed.
        with audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(task_id=task_id, pom_hash=digest,
                                         proposals=[item.model_dump() for item in proposals])) + "\n")
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pom-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return digest
