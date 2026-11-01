"""Run original classes and independent native boundary fixtures under isolated controls."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first
from models.unit_verification_boundary import UnitVerificationBoundary
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.boundary_case import BoundaryCase
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.controlled_inputs import generate_boundary_cases


ROOT = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'


def controlled_unit(tool):
    context = (ROOT / 'com/ibm/dse/base/Context.java').read_text()
    at = context.rfind('}')
    context = context[:at] + 'public Object removeValueAt(String name) { return values.remove(name); }\n' + context[at:]
    value = unit(sources=[source('context', context), source('tag', (ROOT / 'com/ibm/dse/base/Tag.java').read_text()),
        source('settings', 'package example; public class Settings { public static String flag="default"; public static void configure(java.util.Set<String> flags) { flag=flags.iterator().next(); } }'),
        source('external', 'package example; public class External { public static String balance(String name) { throw new AssertionError("Must be replayed"); } public static int code(int n) { throw new AssertionError("Must be replayed"); } }'),
        source('work', '''package example; public class Work {
            private com.ibm.dse.base.Context context;
            public void setContext(com.ibm.dse.base.Context value) { context=value; }
            public int execute() {
                context.setValueAt("balance", External.balance("client"));
                context.setValueAt("code", External.code(1));
                context.setValueAt("clock", new java.util.Date());
                context.setValueAt("random", String.valueOf(new java.util.Random().nextInt(100)));
                context.setValueAt("setting", Settings.flag);
                if (context.getValueAt("input") == null) context.setValueAt("input", "missing");
                context.removeValueAt("old");
                return 0;
            }
        }''')])
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(value), tool_jar=tool)))
    native = '''package example;
        import il.co.dcd.verification.harness.BoundaryAdapter;
        public class NativeAdapter implements BoundaryAdapter {
            public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element configuration) {
                context.put("balance", External.balance("client"));
                context.put("code", External.code(1));
                context.put("clock", new java.util.Date());
                context.put("random", String.valueOf(new java.util.Random().nextInt(100)));
                context.put("setting", Settings.flag);
                if (context.get("input") == null) context.put("input", "missing");
                context.remove("old"); return 0;
            }
        }'''
    sources = [dict(path='example/NativeAdapter.java', content=native)]
    sources += [dict(path='example/' + name + '.java', content=next(item['content'] for item in value['sources'] if item['identity'] == name.lower()))
                for name in ('External', 'Settings')]
    legacy_binding = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter',
        external_bindings={'example.External.balance(java.lang.String)': 'balance', 'example.External.code(int)': 'code'})
    native_binding = BoundaryHarnessBinding(adapter_class='example.NativeAdapter', sources=sources,
        external_bindings={'example.External.balance(java.lang.String)': 'balance', 'example.External.code(int)': 'code'},
        settings_bindings={'example.Settings.configure': {'class': 'nativefixture.Settings', 'method': 'configure'}})
    native_binding.sources[0].content = native_binding.sources[0].content.replace('Settings.flag', 'nativefixture.Settings.flag')
    settings_source = next(item for item in native_binding.sources if item.path.endswith('/Settings.java'))
    settings_source.path = 'nativefixture/Settings.java'
    settings_source.content = settings_source.content.replace('package example;', 'package nativefixture;')
    cases = [BoundaryCase(case_id='controlled-' + str(index), initial_context={'old': 'remove', **({'input': 'provided'} if index else {})},
        clock_millis=1234567890000 + index, random_seed=42,
        settings=[{'class': 'example.Settings', 'method': 'configure', 'arguments': [['configured']]}],
        external_responses=[{'target': 'balance', 'arguments': ['client'], 'value': '10'}, {'target': 'code', 'arguments': [1], 'value': 7}]) for index in range(2)]
    return value, boundary, legacy_binding, native_binding, cases


def test_controls_state_reset_replay_removals_and_branch_coverage(boundary_tool, tmp_path):
    value, boundary, legacy, native, cases = controlled_unit(boundary_tool)
    report = verify_boundary(value, boundary, legacy, native, cases, tmp_path / 'controlled', tool=boundary_tool, candidate_label='independent_native_test_fixture')
    assert report.status == 'matched_observed_cases', report.model_dump_json(indent=2)
    assert not report.acceptance_gate_enabled and not report.exhaustive_equivalence
    assert all(item['legacy']['context']['setting'] == 'configured' for item in report.cases)
    assert report.cases[0]['legacy']['context']['random'] == report.cases[1]['legacy']['context']['random']
    assert report.cases[0]['legacy']['context']['clock'] == {'$date_millis': cases[0].clock_millis}
    assert all(field['result'] == 'matched' for field in report.cases[0]['field_results'])
    assert any({'true', 'false'} <= set(item['observed_outcomes']) for item in report.coverage['branches'])
    assert (tmp_path / 'controlled/boundary-comparison.json').is_file()


def test_missing_external_response_is_incomplete_even_when_caught(boundary_tool, tmp_path):
    value, boundary, legacy, native, cases = controlled_unit(boundary_tool)
    cases[0].external_responses = []
    report = verify_boundary(value, boundary, legacy, native, cases[:1], tmp_path / 'missing', tool=boundary_tool, candidate_label='fixture')
    assert report.status == 'verification_incomplete'


def test_unknown_io_and_stale_source_fail_closed(boundary_tool, tmp_path):
    value, boundary, legacy, native, cases = controlled_unit(boundary_tool)
    changed = deepcopy(value); changed['sources'][0]['content'] += '\n// changed'
    report = verify_boundary(changed, boundary, legacy, native, cases, tmp_path / 'changed', tool=boundary_tool, candidate_label='fixture')
    assert report.status == 'verification_incomplete'
    assert report.issues
    native.sources[0].content = native.sources[0].content.replace('context.put("balance",', 'java.nio.file.Files.readString(java.nio.file.Path.of("must-not-read")); context.put("balance",')
    io_report = verify_boundary(value, boundary, legacy, native, cases, tmp_path / 'unknown-io', tool=boundary_tool, candidate_label='fixture')
    assert io_report.status == 'verification_incomplete'
    assert any('Uncontrolled external dependency' in issue for issue in io_report.issues)


def test_real_output_difference_names_input_path_and_checklist_items(boundary_tool, tmp_path):
    value, boundary, legacy, native, cases = controlled_unit(boundary_tool)
    native.sources[0].content = native.sources[0].content.replace('return 0;', 'return 1;')
    result = verify_boundary(value, boundary, legacy, native, cases[:1], tmp_path / 'different', tool=boundary_tool, candidate_label='fixture')
    assert result.status == 'differences_found', result.model_dump_json(indent=2)
    difference = next(item for item in result.cases[0]['differences'] if item['path'] == 'output')
    assert difference['related_checklist_ids']
    assert next(item for item in result.cases[0]['field_results'] if item['field'] == 'output')['result'] == 'different'
    assert result.cases[0]['case']['clock_millis'] == cases[0].clock_millis


def test_timeout_stops_remaining_cases_as_incomplete(boundary_tool, tmp_path):
    value, boundary, legacy, native, cases = controlled_unit(boundary_tool)
    native.sources[0].content = '''package example; public class NativeAdapter implements il.co.dcd.verification.harness.BoundaryAdapter {
        public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element config) { while (true) {} }
    }'''
    result = verify_boundary(value, boundary, legacy, native, cases, tmp_path / 'timeout', tool=boundary_tool, candidate_label='fixture', case_timeout=2)
    assert result.status == 'verification_incomplete'
    assert len(result.cases) == 1 and result.unexecuted_case_ids == [cases[1].case_id]


def test_loop_and_switch_probes_preserve_original_execution(boundary_tool, tmp_path):
    value, _, legacy, native, _ = controlled_unit(boundary_tool)
    work = '''package example; public class Work {
        public void setContext(com.ibm.dse.base.Context context) {}
        public int execute() {
            int n=0; while(n<2) n++; do { n--; } while(n>1);
            for(int i=0;i<2;i++) n++;
            n += switch(n) { case 3 -> { yield 4; } default -> 0; };
            for(int item : new int[]{1,2}) n += item;
            try { if(n>0) throw new IllegalArgumentException(); } catch(IllegalArgumentException failure) { n++; }
            return n;
        }
        public String unusedOtherDirection() throws Exception { return java.nio.file.Files.readString(java.nio.file.Path.of("never-read")); }
    }'''
    next(item for item in value['sources'] if item['identity'] == 'work').update(source('work', work))
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(value), tool_jar=boundary_tool)))
    native.sources[0].content = '''package example; public class NativeAdapter implements il.co.dcd.verification.harness.BoundaryAdapter {
        public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element config) { return 11; }
    }'''
    result = verify_boundary(value, boundary, legacy, native, [BoundaryCase(case_id='loops')], tmp_path / 'loops', tool=boundary_tool, candidate_label='fixture')
    assert result.status == 'matched_observed_cases', result.model_dump_json(indent=2)
    assert any(branch['detail'] == 'foreach' and set(branch['observed_outcomes']) == {'true','false'} for branch in result.coverage['branches'])


def test_response_prefix_change_is_caught_at_the_executed_boundary(boundary_tool, tmp_path):
    full, _, legacy, _, _ = controlled_unit(boundary_tool)
    nil = json.dumps('<Value xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>')
    formatter = 'package example; public class Formatter { public String format(com.ibm.dse.base.Context context) { '
    formatter += 'return context.getValueAt("value") == null ? ' + nil + ' : "<Value></Value>"; } }'
    value = unit('response_format', 'example.Formatter', [item for item in full['sources'] if item['identity'] in {'context','tag'}] + [source('formatter', formatter)])
    value['effective_configuration']['children'][0]['decorators'] = []
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(value), tool_jar=boundary_tool)))
    content = 'package fixture; public class NativeResponse implements il.co.dcd.verification.harness.BoundaryAdapter { '
    content += 'public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element config) { '
    content += 'return context.get("value") == null ? ' + nil + ' : "<Value></Value>"; } }'
    native = BoundaryHarnessBinding(adapter_class='fixture.NativeResponse', sources=[dict(path='fixture/NativeResponse.java', content=content)])
    cases = [BoundaryCase(case_id='nil', initial_context={'value': None}), BoundaryCase(case_id='empty', initial_context={'value': ''})]
    good = verify_boundary(value, boundary, legacy, native, cases, tmp_path / 'response-good', tool=boundary_tool, candidate_label='native_response_fixture')
    assert good.status == 'matched_observed_cases', good.model_dump_json(indent=2)
    native.sources[0].content = content.replace('xsi', 'wtc')
    changed = verify_boundary(value, boundary, legacy, native, cases, tmp_path / 'response-prefix', tool=boundary_tool, candidate_label='deliberate_prefix_defect_fixture')
    assert changed.status == 'differences_found', changed.model_dump_json(indent=2)
    assert changed.cases[0]['differences'] and not changed.cases[1]['differences']
    generated = generate_boundary_cases(value, boundary)
    assert any('value' in case.initial_context and case.initial_context['value'] is None for case in generated)
    assert any('value' not in case.initial_context for case in generated)


def test_context_case_generation_uses_evidenced_keys_and_keeps_missing_distinct(boundary_tool):
    value, boundary, _, _, _ = controlled_unit(boundary_tool)
    cases = generate_boundary_cases(value, boundary, context_defaults={'input': 'baseline'})
    assert cases == generate_boundary_cases(value, boundary, context_defaults={'input': 'baseline'})
    assert any('input' not in case.initial_context for case in cases)
    assert any(case.initial_context.get('input') == '' for case in cases)
    assert any('old' in case.initial_context for case in cases)


def test_logging_level_receiver_and_caught_exception_are_observable(boundary_tool, tmp_path):
    value, _, legacy, native, _ = controlled_unit(boundary_tool)
    body = '''try { throw new IllegalArgumentException("trigger"); } catch (Exception failure) {
        java.util.logging.Logger.getLogger("fixture").log(java.util.logging.Level.WARNING, "expected", failure);
    } return 0;'''
    work = 'package example; public class Work { public void setContext(com.ibm.dse.base.Context context) {} public int execute() {' + body + '} }'
    next(item for item in value['sources'] if item['identity'] == 'work').update(source('work', work))
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(value), tool_jar=boundary_tool)))
    native.sources[0].content = 'package example; public class NativeAdapter implements il.co.dcd.verification.harness.BoundaryAdapter {'
    native.sources[0].content += 'public Object invoke(String xml, java.util.Map<String,Object> context, org.w3c.dom.Element config) {' + body + '} }'
    result = verify_boundary(value, boundary, legacy, native, [BoundaryCase(case_id='logging')], tmp_path / 'logging', tool=boundary_tool, candidate_label='fixture')
    assert result.status == 'matched_observed_cases', result.model_dump_json(indent=2)
    event = result.cases[0]['legacy']['external_calls'][0]
    assert event['receiver'] == 'fixture'
    assert event['arguments'][0] == {'$logging_level': 'WARNING', 'value': 900}
    assert event['arguments'][2]['exception_type'] == 'java.lang.IllegalArgumentException'
