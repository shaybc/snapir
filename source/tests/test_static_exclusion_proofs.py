"""Exclusions need actual source/configuration proof, not names or observed nonexecution."""
import pytest
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from models.checklist_response import ChecklistResponse
from tools.behavior_verification.boundaries import build_boundary_report
from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first
from test_behavior_static_checks import NATIVE, check, answer_for


def answers_for(original, tool):
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original), tool_jar=tool)))
    assert boundary.parser_checklist.status == 'extracted', boundary.parser_checklist.issues
    answers = UnitChecklistAnswers(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash, responses=[ChecklistResponse(checklist_id=item.id, status='implemented',
            locations=[dict(path=NATIVE[0]['path'], excerpt='return 0;')]) for item in boundary.parser_checklist.items])
    return original, boundary, answers


@pytest.mark.parametrize('mode', ['approved', 'no_contract', 'stale_contract', 'enabled', 'mutated', 'direct_call'])
def test_configuration_guard_requires_pinned_readonly_tag_contract(boundary_tool, mode):
    tag = source('tag', '''package example; public class Tag {
        private final java.util.Map<String,String> values = new java.util.HashMap<>();
        public Tag() {} public Tag(java.util.Map<String,String> attributes) { values.putAll(attributes); }
        public String getAttribute(String key) { return values.get(key); }
        public void clear() { values.clear(); }
    }''')
    work = source('work', '''package example; public class Work {
        public Object initializeFrom(Tag tag) {
            MUTATE
            if ("yes".equals(tag.getAttribute("enabled"))) { System.setProperty("fixture", "disabled-value"); }
            return this;
        }
        public int execute() { DIRECT return 0; }
    }'''.replace('MUTATE', 'tag.clear();' if mode == 'mutated' else '').replace('DIRECT', 'initializeFrom(new Tag());' if mode == 'direct_call' else ''))
    original = unit(sources=[work, tag])
    original['effective_configuration']['attributes']['enabled'] = 'yes' if mode == 'enabled' else 'no'
    data = answers_for(original, boundary_tool)
    item = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == 'disabled-value')
    answer_for(data[2], item.id, status='not_applicable', reason='branch_fixed_off')
    policy = dict(tag_contracts=[] if mode == 'no_contract' else [dict(contract_id='fixture-pure-tag', tag_class='example.Tag',
        source_hash='wrong' if mode == 'stale_contract' else tag['content_hash'], getter='getAttribute')])
    report = check(data, boundary_tool, policy=policy)
    assert report.status == ('mapping_valid' if mode == 'approved' else 'mapping_invalid'), report.errors


@pytest.mark.parametrize('receiver', ['new A()', 'value'])
def test_only_fresh_exact_receiver_can_prune_a_virtual_alternative(boundary_tool, receiver):
    original = unit(sources=[source('work', '''package example; public class Work {
        public int execute() { A value=new A(); return RECEIVER.value(); }
    }'''.replace('RECEIVER', receiver)),
        source('a', 'package example; public class A { public int value() { return 11; } }'),
        source('b', 'package example; public class B extends A { public int value() { return 22; } }')])
    data = answers_for(original, boundary_tool)
    item = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == '22')
    answer_for(data[2], item.id, status='not_applicable', reason='uncertain_target_not_selected')
    report = check(data, boundary_tool)
    assert report.status == ('mapping_valid' if receiver == 'new A()' else 'mapping_invalid'), report.errors


@pytest.mark.parametrize('condition', ['false', 'true'])
def test_other_direction_name_alone_does_not_exempt_a_reachable_method(boundary_tool, condition):
    original = unit('request_unformat', 'example.Formatter', sources=[
        source('context', 'package com.ibm.dse.base; public class Context {}'),
        source('formatter', '''package example; import com.ibm.dse.base.Context; public class Formatter {
            public String format(Context context) { return "outgoing-only"; }
            public void unformat(String xml, Context context) { if (CONDITION) { format(context); } }
        }'''.replace('CONDITION', condition))])
    original['effective_configuration']['children'][0]['decorators'] = []
    data = answers_for(original, boundary_tool)
    item = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == 'outgoing-only')
    answer_for(data[2], item.id, status='not_applicable', reason='other_direction')
    report = check(data, boundary_tool)
    assert report.status == ('mapping_valid' if condition == 'false' else 'mapping_invalid'), report.errors


def test_approved_plumbing_only_covers_the_marker(boundary_tool):
    original = unit(sources=[source('work', 'package example; public class Work { public int execute() throws Exception { return 7; } }')])
    data = answers_for(original, boundary_tool)
    marker = next(item for item in data[1].parser_checklist.items if item.kind == 'exception' and item.detail == 'declared')
    answer_for(data[2], marker.id, status='not_applicable', reason='framework_plumbing', rule_id='throws_declaration_metadata')
    assert check(data, boundary_tool).status == 'mapping_valid'
    assert check(data, boundary_tool, policy=dict(plumbing_rules=[])).status == 'mapping_invalid'


def test_active_unbounded_call_prevents_global_candidate_exclusion(boundary_tool):
    original = unit(sources=[
        source('work', 'package example; public class Work { public int execute() { Missing.touch(); return new A().value(); } }'),
        source('a', 'package example; public class A { public int value() { return 11; } }'),
        source('b', 'package example; public class B extends A { public int value() { return 22; } }')])
    data = answers_for(original, boundary_tool)
    assert any(edge.unbounded for edge in data[1].reachable_slice.edges)
    item = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == '22')
    answer_for(data[2], item.id, status='not_applicable', reason='uncertain_target_not_selected')
    assert check(data, boundary_tool).status == 'mapping_invalid'
