"""Verify a consistent managed conversion contract and explicit model-output errors."""

import json

import pytest

from runtime.managed_conversion_response import managed_instruction, parse_managed_response


def test_format_prompt_replaces_legacy_output_contract():
    from agents.source_conversion.xml_to_java_converter.agent import XML_TO_JAVA_INSTRUCTION
    instruction = managed_instruction(XML_TO_JAVA_INSTRUCTION, "xml_fmtdef")
    assert "<<<SLR_START>>>" not in instruction
    assert "Output TWO items" not in instruction
    assert "Output the DTO class only" not in instruction
    assert "exactly one valid JSON object" in instruction
    assert "Before returning, check" in instruction
    assert "actual whitespace outside strings" in instruction
    assert "service_layer_requirements" in instruction


def test_context_prompt_keeps_rules_and_replaces_source_only_output():
    from agents.source_conversion.context_to_java_converter.agent import CONTEXT_TO_JAVA_INSTRUCTION
    instruction = managed_instruction(CONTEXT_TO_JAVA_INSTRUCTION, "xml_context")
    assert "Output the Java source only" not in instruction
    assert "Getter and setter for every field" in instruction


def test_mixed_response_has_actionable_error():
    with pytest.raises(ValueError, match="Markdown/code fences.*one JSON object"):
        parse_managed_response('```java\npublic class Example {}\n```', "xml_fmtdef")


def test_valid_java_response_and_invalid_schema():
    assert parse_managed_response(json.dumps({"java_source": "public class Example {}", "dependencies": []}), "ibm_java") == "public class Example {}"
    with pytest.raises(ValueError, match="required conversion schema"):
        parse_managed_response('{"java_source": "example"}', "ibm_java")


def test_format_response_validates_embedded_requirements():
    payload = {"java_source": "public class Example {}", "dependencies": [],
               "service_layer_requirements": {"format_id": "Example", "channel": "INTERNET",
                                              "field_transformations": [], "db_lookups": []}}
    assert parse_managed_response(json.dumps(payload), "xml_fmtdef") == payload["java_source"]
    del payload["service_layer_requirements"]["channel"]
    with pytest.raises(ValueError, match="required conversion schema"):
        parse_managed_response(json.dumps(payload), "xml_fmtdef")


@pytest.mark.parametrize("label", ["json", "JSON", ""])
def test_enclosing_json_fence_is_cleaned(label):
    payload = json.dumps({"java_source": "public class Example {}", "dependencies": []})
    assert parse_managed_response("  \n```" + label + "\r\n" + payload + "\r\n```\n", "ibm_java") == "public class Example {}"


@pytest.mark.parametrize("response", [
    'Explanation\n```json\n{}\n```',
    '```json\n{}\n```\nExplanation',
    '```json\n{}\n```\n```json\n{}\n```',
    '```json\n{broken}\n```',
    '```json\n{}',
])
def test_cleaner_does_not_accept_mixed_or_malformed_response(response):
    with pytest.raises(ValueError, match="one JSON object"):
        parse_managed_response(response, "ibm_java")


def test_fenced_json_still_requires_conversion_schema():
    with pytest.raises(ValueError, match="required conversion schema"):
        parse_managed_response('```json\n{"java_source": "example"}\n```', "ibm_java")
