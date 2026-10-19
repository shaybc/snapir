"""Replay Spring XML validation without modifying reviewed service or scenario files."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.service_generation.xml_media_types import has_xml_media_type
from runtime.service_generation.project_output import validate_wrapper_output
from runtime.service_generation.response import parse_service_response


@pytest.mark.parametrize('source', [
    '@RequestMapping(consumes="application/xml", produces="application/xml")',
    'String media = "application/xml;charset=UTF-8";',
    'import org.springframework.http.MediaType; @RequestMapping(consumes=MediaType.APPLICATION_XML_VALUE)',
    'import org.springframework.http.*; response.contentType(MediaType.APPLICATION_XML);',
    '@RequestMapping(consumes=org.springframework.http.MediaType.APPLICATION_XML_VALUE)',
    'import static org.springframework.http.MediaType.APPLICATION_XML_VALUE; @RequestMapping(consumes=APPLICATION_XML_VALUE)',
    'import static org.springframework.http.MediaType.*; response.contentType(APPLICATION_XML);',
])
def test_xml_literal_and_spring_constant_forms(source):
    assert has_xml_media_type(source)


@pytest.mark.parametrize('source', [
    '// "application/xml"\n// MediaType.APPLICATION_XML_VALUE',
    '/* import org.springframework.http.MediaType; MediaType.APPLICATION_XML */',
    'String text="MediaType.APPLICATION_XML_VALUE";',
    'import org.springframework.http.MediaType;',
    'import static org.springframework.http.MediaType.APPLICATION_XML_VALUE;',
    'import example.MediaType; MediaType.APPLICATION_XML_VALUE;',
    'import org.springframework.http.MediaType; MediaType.APPLICATION_XML_VALUE_OTHER;',
    'import org.springframework.http.MediaType; MediaType.APPLICATION_JSON_VALUE;',
])
def test_comments_unused_imports_and_unrelated_constants_do_not_supply_xml(source):
    assert not has_xml_media_type(source)


def test_latest_responses_pass_xml_check_and_other_guards_remain(tmp_path, monkeypatch):
    # Resource isolation has its own replay tests; this replay targets XML binding.
    monkeypatch.setattr('runtime.service_generation.operation_wiring.validate_startup_substitutes', lambda *args: None)
    fixtures = Path(__file__).parent / 'fixtures'
    responses = json.loads((fixtures / 'latest_xml_media_responses.json').read_text(encoding='utf-8'))
    contract = json.loads((fixtures / 'latest_annotated_bean_failure.json').read_text())['contract']
    pom = tmp_path / 'pom.xml'
    pom.write_text('<project/>')
    context = SimpleNamespace(pom_path=str(pom), allowed_ibm_classes=[])
    first, second, third = [parse_service_response(response)['files'] for response in responses]
    # Console diagnostics redact password values; restore a deployment placeholder
    # only in the disposable replay so the independent wiring guard can run.
    for files in (first, second, third):
        for name in files:
            if name.endswith('application.properties'):
                files[name] = files[name].replace('spring.datasource.password=[REDACTED]}',
                                                  'spring.datasource.password=${DB_PASSWORD}')
    with pytest.raises(ValueError, match='executable Spring wiring test'):
        validate_wrapper_output(first, {}, 'TransferFundsOp', context,
                                behavior_units=True, operation_contract=contract)
    for files in (second, third):
        before = dict(files)
        assert validate_wrapper_output(files, {}, 'TransferFundsOp', context,
                                       behavior_units=True, operation_contract=contract) == files
        assert files == before
    with pytest.raises(ValueError, match='changed approved source'):
        validate_wrapper_output(third, {next(iter(third)): 'approved content'}, 'TransferFundsOp', context,
                                behavior_units=True, operation_contract=contract)
    broken = dict(third)
    broken['src/main/java/example/Binding.java'] = 'import jakarta.xml.bind.JAXBContext;'
    with pytest.raises(ValueError, match='Jackson XML'):
        validate_wrapper_output(broken, {}, 'TransferFundsOp', context,
                                behavior_units=True, operation_contract=contract)
    no_xml = {name: content.replace('APPLICATION_XML_VALUE', 'APPLICATION_JSON_VALUE')
              .replace('APPLICATION_XML', 'APPLICATION_JSON') for name, content in third.items()}
    with pytest.raises(ValueError, match='Jackson XML'):
        validate_wrapper_output(no_xml, {}, 'TransferFundsOp', context,
                                behavior_units=True, operation_contract=contract)
