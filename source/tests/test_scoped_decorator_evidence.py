"""Follow mapped decorator implementations and their transitive sources into AI evidence."""

import json
from pathlib import Path

from test_scoped_closure import import_workspace, profiled
from test_scoped_vault_identity import scoped_mapper
from test_scoped_workflow import settings
from tools.conversion_tools.scoped_workflow.units import build_scoped_units
from runtime.behavior_conversion.request_context import encode_request
from agents.behavior_conversion.format_mapping import INSTRUCTION


def test_mapped_decorator_parent_and_helper_reach_model_request(tmp_path, scoped_mapper):
    def change(root):
        java = root / 'src/example'
        (java / 'FirstDecorator.java').write_text(
            'package example;\nimport example.support.AttributeBase;\n'
            'public class FirstDecorator extends AttributeBase { '
            'public boolean enabled(boolean channel) { return configured(channel); } }')
        support = java / 'support'
        support.mkdir()
        (support / 'AttributeBase.java').write_text(
            'package example.support;\npublic class AttributeBase { '
            'protected boolean configured(boolean channel) { return Policy.enabled(channel); } }')
        (support / 'Policy.java').write_text(
            'package example.support;\npublic class Policy { '
            'public static boolean enabled(boolean channel) { return channel; } }')
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', '\n'.join(item.detail for item in closure.blocking_issues)
    expected = {'example.FirstDecorator', 'example.support.AttributeBase', 'example.support.Policy'}
    origins = {item['fqcn']: item for item in closure.java_origins}
    assert expected <= origins.keys()
    config, profile = settings(root, vault)
    units, _ = build_scoped_units(conn, config, closure, profile=profile)
    unit = next(item for item in units if item.occurrence_id == 'csRequestFormat')
    request, encoded = encode_request(unit.model_dump(mode='json'), INSTRUCTION, 1000000)
    sources = {item['identity']: item['content'] for item in json.loads(encoded)['sources']}
    for name in expected:
        origin = origins[name]
        assert sources[origin['definition_id']] == Path(origin['source_file']).read_text()
    assert 'FirstDecorator' in str(request['effective_configuration'])
    assert 'runtime context/configuration dependencies as typed parameters' in INSTRUCTION


def test_contract_and_format_instructions_preserve_runtime_dependencies():
    from agents.behavior_conversion.contract_extraction import INSTRUCTION as CONTRACT
    from runtime.composer_behavior_context import required_composer_behavior
    assert 'superclasses and supporting sources before defining APIs' in CONTRACT
    assert 'runtime context/configuration branches through explicit typed' in CONTRACT
    assert 'tag name or null value alone does not establish an XML nil policy' in INSTRUCTION
    assert 'unresolved_questions' in INSTRUCTION
    decorators = next(item['content'] for item in required_composer_behavior()
                      if '### What a Decorator Is' in item['content'])
    assert 'implementation and transitive Java source evidence determine behavior' in decorators
    assert 'Sets `xsi:nil="true"` when value is null/empty' not in decorators
