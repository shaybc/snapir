"""Exercise parser inventories without AI judgments, legacy execution or acceptance changes."""

from copy import deepcopy
from xml.etree import ElementTree
import pytest

from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.java_tool import analyze_entries
from tools.behavior_verification.reachable_slice import read_reachable_slice
from tools.behavior_verification.parser_checklist import read_parser_checklist


def checklist(value, tool):
    boundary = first(build_boundary_report(prepared(value), tool_jar=tool))
    result = boundary['parser_checklist']
    assert boundary['analysis_status'] == 'identified', boundary['issues']
    assert result['status'] == 'extracted', result['issues']
    assert result['verification_status'] == 'not_run' and not result['acceptance_gate_enabled']
    return result


def test_literals_references_and_defaults_keep_revision_bound_values(boundary_tool):
    value = unit(sources=[source('work', r'''package example; public class Work {
        static final String PREFIX = "xsi:nil";
        private String pattern = "yyyyMMdd";
        private int count;
        public int execute() {
            String text = "quote\" slash\\ newline\n nul\0";
            char character = '\t'; boolean flag = true; double fraction = 1.5;
            String empty = null;
            String surrogate = "\uD800";
            java.time.DayOfWeek day = java.time.DayOfWeek.MONDAY;
            return PREFIX.length() + pattern.length() + text.length() + character + count;
        }
    }''')])
    result = checklist(value, boundary_tool)
    values = {item['properties']['value'] for item in result['items'] if item['kind'] == 'literal'}
    assert {'xsi:nil', 'yyyyMMdd', 'quote" slash\\ newline\n nul\0', '\t', 'true', '1.5', 'null', '\ud800'} <= values
    constants = [item for item in result['items'] if item['kind'] == 'constant_reference'
                 and item['properties'].get('target') == 'example.Work.PREFIX']
    assert constants and constants[0]['properties']['finality'] == 'final'
    assert constants[0]['candidates']
    assert any(item['detail'] == 'enum_constant' and item['properties']['target'] == 'java.time.DayOfWeek.MONDAY' for item in result['items'])
    assert any(item['kind'] == 'initialization' and item['properties'].get('value') == '0' for item in result['items'])
    assert all(item['source_identity'] == 'work' and item['excerpt'] in value['sources'][0]['content']
               for item in result['items'])


def test_all_branch_shapes_writes_and_exception_syntax_are_kept(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        int field;
        public int execute() throws IllegalStateException {
            int n = 0;
            if (n == 0 && field != 1) n = 1; else n = 2;
            n += field > 0 ? 1 : 2;
            for (int i=0; i<2; i++) n++;
            for (String s : new String[]{"value"}) n += s.length();
            while (n < 10) ++n;
            do { n--; } while (n > 10);
            switch (n) { case 1: n=2; break; default: n=3; }
            n = switch(n) { case 1 -> 2; default -> { yield 3; } };
            try { if (field == 0) throw new IllegalStateException("wrapped"); }
            catch (IllegalStateException exception) { n++; }
            finally { field = n; }
            assert n >= 0 : "negative";
            return n;
        }
    }''')])
    result = checklist(value, boundary_tool)
    kinds = {(item['kind'], item['detail']) for item in result['items']}
    assert {('branch', detail) for detail in ('if', 'short_circuit', 'ternary', 'for_guard', 'foreach',
            'while_guard', 'do_guard', 'switch', 'switch_case', 'try', 'catch', 'assert')} <= kinds
    assert {('write', detail) for detail in ('assignment', 'variable_initializer', 'increment_decrement', 'return', 'yield')} <= kinds
    assert {('exception', detail) for detail in ('declared', 'caught', 'thrown', 'finally', 'assertion')} <= kinds
    caught = next(item for item in result['items'] if item['kind'] == 'exception' and item['detail'] == 'caught')
    assert caught['properties']['handler_throw_syntax'] == 'no_explicit_throw'


def test_external_arguments_unknown_effects_and_unbounded_calls_are_explicit(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() {
            java.util.Map<String,String> attributes = new java.util.HashMap<>();
            attributes.put("xsi:nil", "true");
            attributes.remove("xsi:nil");
            java.util.Objects.equals("same", "same");
            Missing.call("unknown");
            return 0;
        }
    }''')])
    result = checklist(value, boundary_tool)
    calls = [item for item in result['items'] if item['kind'] == 'call']
    assert any(item['arguments'] == ['"xsi:nil"', '"true"'] and '.put(' in item['properties']['target'] for item in calls)
    assert any(item['properties'].get('target_scope') == 'external' and '.put(' in item['properties']['target'] for item in calls)
    assert any(item['arguments'] == ['"same"', '"same"'] for item in calls)
    assert any(item['properties']['binding_status'] == 'unbounded' and item['arguments'] == ['"unknown"'] for item in calls)
    assert result['reachability_status'] == 'verification_incomplete'
    assert any(item['kind'] == 'write' and item['properties'].get('certainty') == 'potential_effect_only' for item in result['items'])
    assert any(item['kind'] == 'write' and item['arguments'] == ['"xsi:nil"', '"true"'] for item in result['items'])


def test_resource_close_and_caught_rethrow_are_retained(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() throws Exception {
            try (java.io.StringReader reader = new java.io.StringReader("text")) { return reader.read(); }
            catch (Exception exception) { throw new IllegalStateException("wrapper", exception); }
        }
    }''')])
    result = checklist(value, boundary_tool)
    assert any(item['detail'] == 'resource_cleanup' for item in result['items'])
    assert any(item['kind'] == 'call' and item['properties']['binding_kind'] == 'implicit_resource_close' for item in result['items'])
    assert any(item['kind'] == 'exception' and item['properties'].get('handler_throw_syntax') == 'contains_throw' for item in result['items'])


def test_unused_method_literals_are_excluded_and_ids_are_deterministic(boundary_tool):
    content = '''package example; public class Work {
        public int execute() { return helper("included"); }
        private int helper(String value) { return value.length(); }
        public String otherDirection() { return "excluded"; }
    }'''
    value = unit(sources=[source('work', content)])
    first_result = checklist(value, boundary_tool)
    assert first_result == checklist(deepcopy(value), boundary_tool)
    assert not any(item['properties'].get('value') == 'excluded' for item in first_result['items'])
    changed = checklist(unit(sources=[source('work', content.replace('included', 'changed'))]), boundary_tool)
    assert not {item['id'] for item in first_result['items']} & {item['id'] for item in changed['items']}


def test_text_blocks_signed_bounds_guards_and_comments_are_parsed(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() {
            // "not a literal" if (invented) throw invented;
            String text = """
                line one
                line two
                """;
            Object object = text;
            int n = -7;
            for (;;) { if (n == 0) break; n++; continue; }
            return switch(object) { case String s when s.length() > 0 -> n; default -> 0; };
        }
    }''')])
    result = checklist(value, boundary_tool)
    assert any(item['detail'] == 'TextBlockLiteralExpr' and 'line one\nline two' in item['properties']['value'] for item in result['items'])
    assert any(item['detail'] == 'signed_number' and item['properties']['value'] == '-7' for item in result['items'])
    assert {'break', 'continue', 'switch_guard'} <= {item['detail'] for item in result['items'] if item['kind'] == 'branch'}
    assert not any(item['properties'].get('value') == 'not a literal' for item in result['items'])


def test_item_certainty_follows_original_code_node_and_never_claims_execution(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() { return helper(); }
        public int helper() { return 7; }
    }''')])
    boundary = first(build_boundary_report(prepared(value), tool_jar=boundary_tool))
    paths = {node['id']: node['path_certainty'] for node in boundary['reachable_slice']['nodes']}
    assert all(item['path_certainty'] == paths[item['code_node_id']] for item in boundary['parser_checklist']['items'])
    assert {'certain', 'uncertain'} <= {item['path_certainty'] for item in boundary['parser_checklist']['items']}


@pytest.mark.parametrize('change', ['hash', 'body', 'candidate', 'duplicate', 'range', 'property', 'id'])
def test_invalid_checklist_provenance_is_rejected(boundary_tool, change):
    value = unit()
    boundary = boundary_contract(value)
    analysis, _ = analyze_entries({boundary.source_manifest_hash: dict(sources=value['sources'], boundaries=[boundary])}, boundary_tool)
    sources = {item['identity']: item for item in value['sources']}
    boundary.reachable_slice = read_reachable_slice(analysis.find('entry/reachability'), boundary, sources, {})
    element = deepcopy(analysis.find('entry/checklist'))
    item = element.find('item')
    if change == 'hash': item.set('source_hash', 'fabricated')
    elif change == 'body': item.set('code_node_id', 'absent')
    elif change == 'candidate': ElementTree.SubElement(item, 'candidate', id='outside-source')
    elif change == 'duplicate': element.append(deepcopy(item))
    elif change == 'range': item.set('start_column', '99999')
    elif change == 'id': item.set('id', 'check-fabricated')
    else: ElementTree.SubElement(item, 'property', name='invalid', encoding='utf-16be-base64').text = 'not-base64'
    result = read_parser_checklist(element, boundary, sources, {})
    assert result.status == 'verification_incomplete' and result.issues and not result.items
