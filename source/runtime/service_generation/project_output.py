"""Validate wrapper files without permitting changes to reviewed business code."""

from pathlib import Path

from agents.java_service_generation.agent import parse_generated_project_output, validate_generated_project

WRAPPER_OUTPUT_VERSION = "managed-pom-rejection-v1"


def configure_executable_build(context):
    """Add the pinned Spring Boot packaging plugin without accepting model build scripts."""
    from constants import SPRING_BOOT_VERSION
    from xml.etree import ElementTree
    from tools.maven_dependency_tools.pom_manager import project_lock
    path = Path(context.pom_path)
    with project_lock(path):
        root = ElementTree.parse(path).getroot()
        namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
        build = root.find(namespace + "build")
        if build is None:
            build = ElementTree.SubElement(root, namespace + "build")
        plugins = build.find(namespace + "plugins")
        if plugins is None:
            plugins = ElementTree.SubElement(build, namespace + "plugins")
        plugin = ElementTree.SubElement(plugins, namespace + "plugin")
        for name, text in (("groupId", "org.springframework.boot"),
                           ("artifactId", "spring-boot-maven-plugin"), ("version", SPRING_BOOT_VERSION)):
            ElementTree.SubElement(plugin, namespace + name).text = text
        execution = ElementTree.SubElement(ElementTree.SubElement(plugin, namespace + "executions"), namespace + "execution")
        goals = ElementTree.SubElement(execution, namespace + "goals")
        ElementTree.SubElement(goals, namespace + "goal").text = "repackage"
        path.write_bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))


def validate_wrapper_output(output, protected, operation_id, context, *, behavior_units=False, operation_contract=None):
    """Accept source/resources only and validate the complete protected project."""
    files = parse_generated_project_output(output)
    normalized = {}
    for name, content in files.items():
        name = name.replace("\\", "/")
        if name.startswith("/") or ":" in name or ".." in Path(name).parts:
            raise ValueError("Unsafe generated wrapper path")
        if not name.startswith(("src/main/java/", "src/main/resources/", "src/test/java/", "src/test/resources/")):
            raise ValueError("Wrapper output may contain only Java sources and resources; remove " + name
                             + " from files. Maven POMs are managed by the converter; return Maven dependency proposals in dependencies, not a pom.xml file.")
        if name.lower().endswith((".jar", ".class")):
            raise ValueError("Binary library copying is prohibited")
        if name in protected and protected[name] != content:
            raise ValueError("Wrapper generation changed approved source: " + name)
        if name in normalized:
            raise ValueError("Duplicate normalized wrapper path")
        normalized[name] = content
    combined = {**protected, **normalized, "pom.xml": Path(context.pom_path).read_text(encoding="utf-8")}
    if behavior_units:
        from runtime.service_generation.operation_wiring import validate_operation_wiring
        validate_operation_wiring(normalized, operation_contract)
        from tools.validation_tools.ibm_dependency_guard_tool import scan_source
        from constants import FORBIDDEN_DEPENDENCIES
        issues = ["Prohibited wrapper dependency: " + finding for content in normalized.values()
                  for finding in scan_source(content, FORBIDDEN_DEPENDENCIES, allowed_classes=context.allowed_ibm_classes)]
        if not any(name.endswith("application.properties") for name in combined):
            issues.append("Native service configuration is missing")
        if not any(name.startswith("src/test/java/") for name in combined):
            issues.append("Native service tests are missing")
        java = "\n".join(normalized.values())
        from runtime.service_generation.xml_media_types import has_xml_media_type
        if not any(has_xml_media_type(content) for name, content in normalized.items()
                   if name.endswith(".java")) or "jakarta.xml.bind" in java:
            issues.append("Native service must configure Jackson XML request/response binding")
    else:
        issues = validate_generated_project(combined, operation_id, build_context=context)
    # Assembly owns the real Service class; generation must wrap, not rename it.
    issues = [issue for issue in issues if issue != f"missing required file: service/{operation_id}ServiceImpl.java"]
    if issues:
        raise ValueError("; ".join(issues))
    java = "\n".join(normalized.values())
    if "@SpringBootApplication" not in java or "@RestController" not in java:
        raise ValueError("Generated project requires Spring Boot application and REST controller")
    if "TODO" in java or "UnsupportedOperationException" in java:
        raise ValueError("Generated wrappers contain unfinished implementation")
    return normalized
