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
    assert origins['example.Work']['definition_id'] not in sources
    step = next(item for item in units if item.kind == 'configured_step')
    assert {item.identity for item in step.sources} == {origins['example.Work']['definition_id']}
    assert step.referenced_definitions == []
    assert {item['attributes']['id'] for item in unit.referenced_definitions} == {'Leaf'}
    assert '4. Runtime Execution Model' not in {item['heading'] for item in request['composer_behavior_evidence']}
    assert '6. Formats and the Format/Unformat Process' in {item['heading'] for item in request['composer_behavior_evidence']}
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


def test_real_formatter_dependency_is_kept_even_when_also_used_by_step(tmp_path, scoped_mapper):
    def change(root):
        (root / 'src/example/Field.java').write_text(
            'package example;\npublic class Field { Work dependency; }')
        (root / 'src/example/Work.java').write_text(
            'package example;\npublic class Work { Field dependency; }')
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    closure = profiled(conn, root)
    assert closure.status == 'evidence_ready', closure.blocking_issues
    config, profile = settings(root, vault)
    units, _ = build_scoped_units(conn, config, closure, profile=profile)
    origins = {item['fqcn']: item for item in closure.java_origins}
    response = next(item for item in units if item.occurrence_id == 'csReplyFormat')
    assert {source.identity for source in response.sources} == {
        origins[name]['definition_id'] for name in ('example.Field', 'example.Work')}
    assert response.referenced_definitions == []


def test_old_operation_wide_evidence_requires_fresh_preparation():
    from types import SimpleNamespace
    import pytest
    from tools.conversion_tools.scoped_workflow.unit_evidence import java_evidence
    closure = SimpleNamespace(java_origins=[dict(fqcn='example.Field', status='verified_source')],
                              external_dependencies=[])
    with pytest.raises(ValueError, match='refresh preparation'):
        java_evidence(closure, {'example.Field'})


def test_format_manual_scope_survives_extraction_and_review_wrappers():
    from runtime.composer_behavior_context import attach_composer_behavior
    scope = dict(kind='request_unformat', schema_version='scoped-v3-c5')
    for payload in (scope, dict(subject_scope=scope), dict(unit=scope)):
        headings = {item['heading'] for item in attach_composer_behavior(payload)['composer_behavior_evidence']}
        assert headings == {'5. Context', '6. Formats and the Format/Unformat Process', '7. Decorators'}
    assert len(attach_composer_behavior(dict(kind='request_unformat'))['composer_behavior_evidence']) == 4
