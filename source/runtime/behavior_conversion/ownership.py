"""Bind configured bundles to native projects and stable managed library versions."""

from pathlib import Path
from models.maven_dependency import MavenDependency
from constants import COMMON_LIB_GROUP_ID
from tools.component_inventory_tools.identity import stable_id


def project_for(config, unit, assignments):
    """Return a shared project or the owning channel-qualified operation project."""
    library = assignments[unit.unit_id]
    if library:
        return Path(config.output_root) / "behavior-libraries" / library
    channel, operation = unit.consumers[0].split("/", 1)
    return Path(config.output_root) / channel / operation


def consumer_artifact(accepted, consumer):
    """Use the consumer's local copy when the threshold did not select sharing."""
    return accepted.get("local_instances", {}).get(consumer, accepted)


def library_dependency(config, project):
    """Use the project's run-local identity; ordinary external versions remain explicit."""
    return MavenDependency(group_id=COMMON_LIB_GROUP_ID, artifact_id=project.name,
        version="1.0.0-" + stable_id(config.run_id)[:12], scope="compile", reason="Accepted native behavior library for this run",
        required_classes=[])


def create_native_context(config, profile, project, factory, *, artifact_id=None):
    """Initialize run-qualified library coordinates without changing Maven settings."""
    from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
    initialize_managed_pom(str(Path(project) / "pom.xml"), COMMON_LIB_GROUP_ID, artifact_id or Path(project).name,
                           version="1.0.0-" + stable_id(config.run_id)[:12], java_version=profile.java_version)
    context = factory(profile, Path(project), artifact_id or Path(project).name)
    configure_native_tests(context.pom_path)
    return context


def configure_native_tests(pom_path):
    """Pin the native projects' JUnit-capable runner without changing repository settings."""
    from xml.etree import ElementTree
    from tools.maven_dependency_tools.pom_manager import project_lock
    path = Path(pom_path)
    with project_lock(path):
        root = ElementTree.parse(path).getroot()
        namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
        if any(node.findtext(namespace + "artifactId") == "maven-surefire-plugin" for node in root.findall(".//" + namespace + "plugin")):
            return
        build = root.find(namespace + "build")
        if build is None:
            build = ElementTree.SubElement(root, namespace + "build")
        plugins = build.find(namespace + "plugins")
        if plugins is None:
            plugins = ElementTree.SubElement(build, namespace + "plugins")
        plugin = ElementTree.SubElement(plugins, namespace + "plugin")
        for name, text in (("groupId", "org.apache.maven.plugins"), ("artifactId", "maven-surefire-plugin"), ("version", "3.5.4")):
            ElementTree.SubElement(plugin, namespace + name).text = text
        path.write_bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
