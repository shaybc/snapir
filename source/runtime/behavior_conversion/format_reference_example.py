"""Load the single verified Jackson/JUnit reference for complete-format requests."""

from pathlib import Path

FORMAT_EXAMPLE_INSTRUCTION = """Follow format_reference_example for working Jackson setup,
XML-specific API usage and focused JUnit test structure in this initial response and every
correction. Use real Jackson and mapper objects, not Mockito mocks of the mapper. Use
ToXmlGenerator.Feature.WRITE_XML_DECLARATION for XML declarations; SerializationFeature
does not declare WRITE_XML_DECLARATION or WRITE_DOC_DECLARATION.
For namespaced attributes, keep localName unprefixed (for example nil) and supply the namespace
URI separately; do not put xsi:nil into localName as well as setting its namespace.
Derive actual wire names, transformations, null semantics and test expectations from the current format evidence,
not the illustrative example values. Reuse current known dependency coordinates, versions
and scopes; the example's verification versions are not dependency overrides."""


def attach_format_reference_example(payload):
    """Attach central source/test files only to complete request/response format units."""
    if payload.get("kind") not in ("request_unformat", "response_format"):
        return False
    folder = Path(__file__).resolve().parents[2] / "templates/native_formats/jackson"
    payload["format_reference_example"] = dict(example_version=1,
        verified_platform=dict(java_version=25, jackson_xml_version="2.15.2", junit_version="5.10.0"),
        files=[dict(path="src/" + ("test" if path.name.endswith("Test.java") else "main") + "/java/example/format/" + path.name,
            content=path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.java"))])
    return True
