"""Versioned Java 25 testing platform, reference examples and candidate safeguards."""

import re
from pathlib import Path
from xml.etree import ElementTree
from models.maven_dependency import MavenDependency
from runtime.java_public_type import _code
from runtime.behavior_conversion.method_contracts import _erase_type_arguments
from tools.maven_dependency_tools.pom_manager import project_lock, merge_dependencies

TEST_REQUIREMENT = dict(requirement_id="java25-test-template", version=1,
    description="Use the verified Java 25 JUnit/Mockito testing platform with small focused behavior tests and separate adapter contract tests; mock external interfaces rather than hand implement them.")
TEST_PINS = (
    ("org.junit.jupiter", "junit-jupiter", "5.10.0"),
    ("org.mockito", "mockito-core", "5.23.0"),
    ("net.bytebuddy", "byte-buddy", "1.17.7"),
    ("net.bytebuddy", "byte-buddy-agent", "1.17.7"),
    ("org.objenesis", "objenesis", "3.3"),
)


def testing_contract(profile):
    """Return the application-owned verified platform only for its supported Java target."""
    if profile.java_version != 25:
        return None
    folder = Path(__file__).resolve().parents[2] / "templates/native_tests/java25"
    dependencies = [MavenDependency(group_id=group, artifact_id=artifact, version=version,
        scope="test", reason="Application-owned Java 25 test template").model_dump(mode="json")
        for group, artifact, version in TEST_PINS]
    return dict(requirement=dict(TEST_REQUIREMENT), java_version=25, dependencies=dependencies,
        rules=["Keep each test focused on one evidenced outcome or side effect.",
               "Cover meaningful behavior across the bundle, not every class individually; wire models and simple helpers may be covered through mapper or caller tests.",
               "The platform policy is checked directly; it needs no coverage entry or unit-contract requirement declaration.",
               "Separate business behavior tests from adapter/infrastructure contract tests.",
               "Use JUnit Jupiter and plain Mockito mock/when/verify calls; no experimental JVM compatibility flags.",
               "Mock external interfaces instead of generating handwritten implementations.",
               "Prefer narrow generated collaborators; do not change accepted production APIs just for tests.",
               "Preserve meaningful assertions and derive expectations from evidence, not from the example values."],
        examples=[dict(path=path.name, content=path.read_text(encoding="utf-8"))
                  for path in sorted(folder.glob("*.java"))])


def attach_testing_contract(payload, profile):
    """Supply trusted pins before prompting; existing ordinary dependency versions stay intact."""
    contract = testing_contract(profile)
    if contract is None:
        return
    payload["testing_contract"] = contract
    known = {(d["group_id"], d["artifact_id"]): d for d in payload.get("known_dependencies", [])}
    for dependency in contract["dependencies"]:
        key = (dependency["group_id"], dependency["artifact_id"])
        if key in known and known[key]["scope"] != "test":
            raise ValueError("Java 25 test template conflicts with non-test dependency: " + ":".join(key))
        known[key] = dependency
    payload["known_dependencies"] = list(known.values())


def validate_testing_contract(bundle, contract):
    """Reject wrong test pins and handwritten external-interface substitutes generically."""
    pins = {(d["group_id"], d["artifact_id"]): d for d in contract["dependencies"]}
    for dependency in bundle.dependencies:
        expected = pins.get((dependency.group_id, dependency.artifact_id))
        if expected and (dependency.version, dependency.scope) != (expected["version"], expected["scope"]):
            raise ValueError(f"Testing requirement {TEST_REQUIREMENT['requirement_id']} v1: {dependency.group_id}:{dependency.artifact_id} "
                f"requires version={expected['version']} scope={expected['scope']}; got version={dependency.version} scope={dependency.scope}. "
                "Use the supplied verified test platform; preserve the behavior assertions.")
    owned_types = {name for file in bundle.files for name in re.findall(r"\b(?:class|interface|enum|record)\s+(\w+)", _code(file.content))}
    for file in bundle.files:
        if not file.path.startswith("src/test/java/"):
            continue
        code = _code(file.content)
        imports = dict((name.split(".")[-1], name) for name in re.findall(r"\bimport\s+([\w.]+)\s*;", code))
        wildcards = re.findall(r"\bimport\s+([\w.]+)\.\*\s*;", code)
        local = set(re.findall(r"\binterface\s+(\w+)", code))
        for declaration in re.findall(r"\bclass\s+\w+[^{}]*?\bimplements\s+([^{}]+)", code):
            for name in re.findall(r"[A-Za-z_$][\w.$]*", _erase_type_arguments(declaration)):
                if name in owned_types:
                    continue
                qualified = imports.get(name, name)
                if qualified == name and name not in local and wildcards:
                    qualified = wildcards[0] + "." + name
                if "." in qualified and not qualified.startswith("com.company.generated."):
                    raise ValueError("Handwritten external-interface test double in " + file.path + ": " + qualified +
                        ". Use the supplied mocking framework and reference examples; do not implement the external interface manually.")


def apply_test_platform(pom_path, contract, verifier, allowed_ibm_artifacts=()):
    """Apply approved test-only pins in a staged POM, verifying every platform artifact."""
    dependencies = [MavenDependency.model_validate(d) for d in contract["dependencies"]]
    for dependency in dependencies:
        verifier(dependency)
    path = Path(pom_path)
    pins = {(d.group_id, d.artifact_id): d for d in dependencies}
    with project_lock(path):
        root = ElementTree.parse(path).getroot()
        for node in root.findall("{*}dependencies/{*}dependency"):
            key = (node.findtext("{*}groupId"), node.findtext("{*}artifactId"))
            if key not in pins:
                continue
            if node.findtext("{*}scope", "compile") != "test":
                raise ValueError("Cannot replace non-test dependency for test template: " + ":".join(key))
            namespace = node.tag.partition("}")[0] + "}" if "}" in node.tag else ""
            version = node.find(namespace + "version")
            if version is None:
                version = ElementTree.SubElement(node, namespace + "version")
            version.text = pins[key].version
        path.write_bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
    merge_dependencies(str(path), dependencies, verifier, allowed_ibm_artifacts=allowed_ibm_artifacts,
                       task_id="java25-test-template-v1")
