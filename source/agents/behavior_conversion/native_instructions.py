"""Shared first-response rules and schema-valid examples for native unit conversion."""

import json

APPROVED_JUNIT_DEPENDENCY = {
    "group_id": "org.junit.jupiter", "artifact_id": "junit-jupiter", "version": "5.10.2",
    "scope": "test", "reason": "JUnit Jupiter tests and execution engine",
    "required_classes": ["org.junit.jupiter.api.Test", "org.junit.jupiter.api.Assertions"],
}

COMMON_INSTRUCTION = """Mandatory target-code contract for the FIRST response and every correction:
Generate ordinary native Java business behavior, not a Composer compatibility runtime.
All original XML, Java source and embedded Composer documentation are behavior evidence
ONLY, including their imports and code examples. They are not reusable target APIs.
No com.ibm imports or executable references in ANY generated main or test file. Do not
copy or rename Context, format/decorator holders, Tag initialization or framework engines.
Use explicit typed inputs/results and plain mapper transformations for decorators.
Reuse supplied accepted native interfaces without changing them. Retain documented ordinary
external dependencies where required; do not invent replacement business behavior.
Reuse known_dependencies coordinates, versions and scopes exactly for EVERY known artifact.
Do not choose new versions for known libraries. Declare only dependencies used by the returned
main/test code; keep required_classes tied to those imports. Propose a new pinned dependency
only when its artifact is absent from known_dependencies and genuinely needed.
Use the supplied current JUnit Jupiter dependency for generated JUnit 5 tests; include it in
dependencies with its current scope (normally scope test). When JUnit is not known, the
approved test dependency below is the fallback, not an override of existing dependencies. Test and Assertions belong to junit-jupiter-api, supplied
transitively by junit-jupiter. The engine executes tests; it is not the API containing
Test/Assertions. required_classes lists actual imported APIs, including test imports.
Keep all other dependency coordinates pinned and justified by generated code.
Return exactly one JSON object matching the supplied schema, with no prose or fences.
Every file path starts with src/main/java/ or src/test/java/, followed by its package
path and public type filename. Never return package-relative paths without these prefixes.
Write constructor names without a package or return type in both Java source and method_signatures: use public ValidationFailedStep(String category, String number), never public com.company.generated.ValidationFailedStep(...).
Declare only constructors and methods that exist in the returned Java, with matching public visibility and parameter types; keep the full package name in type_name.
Before returning EVERY response, check valid JSON syntax and escaped Java strings; verify
unit_contract method metadata matches the actual public Java methods, all imported APIs
have dependencies, and coverage maps every supplied requirement to executable test files.
The example below illustrates response structure and native code style ONLY: adapt its
package, unit ID, evidence IDs, requirements, classes and behavior to the current evidence;
never copy its sample behavior into the real unit. The supplied schema is authoritative.
"""


def response_example(kind, known=()):
    """Return a valid minimal unit bundle illustrating typed code and JUnit metadata."""
    name = "RequestMapper" if kind == "format" else "BusinessStep"
    main = f"package com.company.generated.example; public class {name} {{ public String execute(String value) {{ return value; }} }}"
    test = (f"package com.company.generated.example; import org.junit.jupiter.api.Test; "
            "import static org.junit.jupiter.api.Assertions.assertEquals; "
            f"public class {name}Test {{ @Test public void preservesValue() {{ "
            f'assertEquals("value", new {name}().execute("value"));' + " } }")
    test_path = f"src/test/java/com/company/generated/example/{name}Test.java"
    example = {
        "files": [{"path": f"src/main/java/com/company/generated/example/{name}.java", "content": main},
                  {"path": test_path, "content": test}],
        "dependencies": [dict(APPROVED_JUNIT_DEPENDENCY)],
        "coverage": {"business": [test_path]}, "evidence_ids": ["example-source"],
        "unresolved_questions": [], "input_type": "java.lang.String",
        "output_type": "java.lang.String",
        "unit_contract": {"unit_id": "example-unit", "apis": [{"type_name": f"com.company.generated.example.{name}",
            "method_signatures": ["public java.lang.String execute(java.lang.String)"]}],
            "dependency_units": [], "requirements": {"business": "Preserve the evidenced value"},
            "evidence_ids": ["example-source"]}, "schema_version": "v1",
    }
    if kind == "format":
        example["files"][0]["content"] = (
            'package com.company.generated.example; public class RequestMapper { '
            'public String execute(RequestXml wire) { return wire.value.trim(); } }')
        example["files"][1]["content"] = (
            'package com.company.generated.example; import org.junit.jupiter.api.Test; '
            'import static org.junit.jupiter.api.Assertions.assertEquals; '
            'public class RequestMapperTest { @Test public void removesPadding() { '
            'RequestXml wire = new RequestXml(); wire.value = " value "; '
            'assertEquals("value", new RequestMapper().execute(wire)); } }')
        example["files"].append({"path": "src/main/java/com/company/generated/example/RequestXml.java", "content":
            'package com.company.generated.example; import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement; '
            'import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty; '
            '@JacksonXmlRootElement(localName="Request") public class RequestXml { '
            '@JacksonXmlProperty(localName="Value") public String value; }'})
        example["dependencies"].append({"group_id": "com.fasterxml.jackson.dataformat",
            "artifact_id": "jackson-dataformat-xml", "version": "2.17.2", "scope": "compile",
            "reason": "Example XML wire annotations; use the approved project version in real output",
            "required_classes": ["com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement",
                                 "com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty"]})
        example["input_type"] = example["wire_type"] = "com.company.generated.example.RequestXml"
        example["unit_contract"]["apis"][0]["method_signatures"] = [
            "public java.lang.String execute(com.company.generated.example.RequestXml)"]
        example["unit_contract"]["requirements"]["business"] = "Remove evidenced whitespace padding"
    # Build Java text first; json.dumps below supplies the separate JSON escaping layer.
    quoted_method = r'''@Override public String toString() {
        return "value='" + "\"quoted\"" + '\'' + ", path=C:\\demo";
    }'''
    quoted_test = (r'''@Test public void preservesQuotesAndBackslashes() {
        assertEquals("value='\"quoted\"', path=C:\\demo", new ''' + name + r'''().toString());
    }''')
    example["files"][0]["content"] = example["files"][0]["content"][:-1] + quoted_method + "}"
    example["files"][1]["content"] = example["files"][1]["content"][:-1] + quoted_test + "}"
    example["unit_contract"]["apis"][0]["method_signatures"].append("public java.lang.String toString()")
    current = {(item["group_id"], item["artifact_id"]): item for item in known}
    for dependency in example["dependencies"]:
        existing = current.get((dependency["group_id"], dependency["artifact_id"]))
        if existing:
            dependency.update(version=existing["version"], scope=existing["scope"])
    return example


def native_instructions(kind, known=()):
    """Build shared guidance with approved test coordinates and a JSON response example."""
    junit = dict(APPROVED_JUNIT_DEPENDENCY)
    for dependency in known:
        if (dependency["group_id"], dependency["artifact_id"]) == (junit["group_id"], junit["artifact_id"]):
            junit.update(version=dependency["version"], scope=dependency["scope"])
    return (COMMON_INSTRUCTION + "\nApproved test dependency:\n" +
            json.dumps(junit) + "\nCorrect response example (including escaped Java quotes and backslashes):\n"
            "Write valid Java first, then encode it as JSON. A single quote is not a JSON escape; "
            "never use backslash-apostrophe as a JSON escape. The Java character literal for an apostrophe "
            "still needs its Java backslash, which must itself be escaped in JSON.\n" +
            json.dumps(response_example(kind, known)) + "\nUnit-specific instructions:\n")


def reuse_known_dependencies(instruction, known, java_version=None):
    """Align response examples with current versions and guide every native code request."""
    if instruction.startswith("Mandatory target-code contract"):
        _, specific = instruction.split("\nUnit-specific instructions:\n", 1)
        kind = "format" if "Implement the complete configured format unit" in specific else "step"
        instruction = native_instructions(kind, known) + specific
    else:
        instruction += "\nReuse all known_dependencies coordinates, versions and scopes exactly. " + \
            "Propose pinned new dependencies only for artifacts not in that inventory; " + \
            "declare dependencies required by main and test imports. Never override known versions."
    if java_version is not None:
        instruction += "\n" + java_compatibility_instruction(java_version)
    return instruction


def java_compatibility_instruction(java_version):
    """Require implementation, tests and dependencies to run on the configured JDK."""
    return (f"Configured Java target: Java {java_version}. All generated implementation code, "
            f"test code, and proposed dependencies must support Java {java_version}. "
            f"Tests must compile and execute on Java {java_version}. "
            "Do not assume a testing library is compatible merely because it resolves or compiles. "
            "Preserve existing dependency versions and scopes. If they prevent compatibility with "
            "the configured Java target, report the conflict in unresolved_questions instead of "
            "silently upgrading them or generating incomplete replacements.")
