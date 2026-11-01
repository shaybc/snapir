"""Exercise conservative reachability, initialization provenance and unresolved candidates."""

from copy import deepcopy
from pathlib import Path
import subprocess
from xml.etree import ElementTree

import pytest

from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.reachable_slice import read_reachable_slice
from tools.behavior_verification.boundary_contracts import boundary_contract


def graph(value, tool):
    entry = first(build_boundary_report(prepared(value), tool_jar=tool))
    assert entry['analysis_status'] == 'identified', entry['issues']
    return entry['reachable_slice']


def signatures(result):
    return {node['signature'] for node in result['nodes']}


def formatter():
    sources = [
        source('context', 'package com.ibm.dse.base; public class Context { public void put(String value) { System.out.println("com.ibm.dse.base.Context.put(java.lang.String)"); } }'),
        source('tag', 'package com.ibm.dse.base; public class Tag { public String getAttribute(String name) { System.out.println("com.ibm.dse.base.Tag.getAttribute(java.lang.String)"); return "3"; } }'),
        source('parent', '''package example;
public class Parent {
    static int flag = 1;
    static { flag = 2; }
    protected int seed = 4;
    public Parent() { }
    public void initializeFrom(com.ibm.dse.base.Tag tag) { seed = Integer.parseInt(tag.getAttribute("seed")); }
    protected String shared(String value) { System.out.println("example.Parent.shared(java.lang.String)"); return value; }
}'''),
        source('formatter', '''package example;
public class Formatter extends Parent {
    private int length = 7;
    { length++; }
    public Formatter() { super(); }
    public void initializeFrom(com.ibm.dse.base.Tag tag) {
        System.out.println("example.Formatter.initializeFrom(com.ibm.dse.base.Tag)");
        super.initializeFrom(tag); length = Integer.parseInt(tag.getAttribute("length"));
    }
    public void unformat(String xml, com.ibm.dse.base.Context context) {
        System.out.println("example.Formatter.unformat(java.lang.String, com.ibm.dse.base.Context)");
        context.put(shared(remove(xml)));
    }
    private String remove(String value) {
        System.out.println("example.Formatter.remove(java.lang.String)");
        return value == null ? "" : value.trim();
    }
    public String format(com.ibm.dse.base.Context context) { return shared(add("output")); }
    private String add(String value) { return "<Value>" + value + "</Value>"; }
}''')]
    result = unit('request_unformat', 'example.Formatter', sources)
    result['effective_configuration']['children'][0]['decorators'] = []
    return result


def test_direction_and_all_initialization_forms_are_retained(boundary_tool):
    result = graph(formatter(), boundary_tool)
    names = signatures(result)
    assert result['status'] == 'analyzed', result['issues']
    assert 'example.Formatter.unformat(java.lang.String, com.ibm.dse.base.Context)' in names
    assert 'example.Parent.shared(java.lang.String)' in names
    assert 'example.Formatter.remove(java.lang.String)' in names
    assert any('Parent.initializeFrom' in name for name in names)
    assert any('Formatter.initializeFrom' in name for name in names)
    assert not any('.format(' in name or '.add(' in name for name in names)
    assert {'constructor', 'static_field_initializer', 'instance_field_initializer', 'static_initializer', 'instance_initializer'} <= {
        node['kind'] for node in result['nodes']}
    assert result['roots']['entry'] and result['roots']['initialization']
    assert result['verification_status'] == result['runtime_tracing_status'] == 'not_run'


def test_runtime_trace_of_original_setup_and_entry_is_contained(boundary_tool, tmp_path):
    value = formatter()
    result = graph(value, boundary_tool)
    files = []
    for item in value['sources']:
        name = {'context': 'Context', 'tag': 'Tag', 'parent': 'Parent', 'formatter': 'Formatter'}[item['identity']]
        path = tmp_path / (name + '.java')
        path.write_text(item['content'])
        files.append(path)
    driver = tmp_path / 'TraceDriver.java'
    driver.write_text('''public class TraceDriver {
        public static void main(String[] args) {
            for (String value : new String[] {null, " text "}) {
                example.Formatter formatter = new example.Formatter();
                formatter.initializeFrom(new com.ibm.dse.base.Tag());
                formatter.unformat(value, new com.ibm.dse.base.Context());
            }
        }
    }''')
    compiled = subprocess.run(['javac', '-d', str(tmp_path), *map(str, files), str(driver)], capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    ran = subprocess.run(['java', '-cp', str(tmp_path), 'TraceDriver'], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    observed = set(ran.stdout.splitlines())
    assert observed and observed <= signatures(result)


def test_interface_dispatch_keeps_all_supplied_implementations(boundary_tool):
    value = unit(sources=[
        source('interface', 'package example; public interface Operation { int run(); }'),
        source('first', 'package example; public class First implements Operation { public int run() { return 1; } }'),
        source('second', 'package example; public class Second implements Operation { public int run() { return 2; } }'),
        source('work', 'package example; public class Work { public int execute() { Operation op = new First(); return op.run(); } }')])
    result = graph(value, boundary_tool)
    assert {'example.First.run()', 'example.Second.run()'} <= signatures(result)
    edges = [edge for edge in result['edges'] if edge['declared_target'] == 'example.Operation.run()']
    assert edges and edges[0]['uncertain'] and edges[0]['unbounded']
    assert len(edges[0]['candidates']) == 2
    assert result['status'] == 'verification_incomplete'


def test_xml_setters_are_retained_without_treating_them_as_proven_calls(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        private String fields = "default";
        public void setRequiredFields(String fields) { this.fields = fields; }
        public void setUnrelated(String ignored) { }
        public int execute() { return fields.length(); }
    }''')])
    value['effective_configuration']['attributes']['RequiredFields'] = 'ClientId,AccountNumber'
    result = graph(value, boundary_tool)
    assert 'example.Work.setRequiredFields(java.lang.String)' in signatures(result)
    assert 'example.Work.setUnrelated(java.lang.String)' not in signatures(result)
    assert any(edge['kind'] == 'configured_property_binding' and edge['uncertain'] for edge in result['edges'])


def test_defaults_and_constructor_delegation_are_explicit(boundary_tool):
    value = unit(sources=[
        source('parent', 'package example; public class Parent { public Parent(int n) {} }'),
        source('work', '''package example; public class Work extends Parent {
            private String text; private int number; private boolean enabled; private char character;
            public Work() { this(2); }
            private Work(int n) { super(n); }
            public int execute() { return number; }
        }''')])
    result = graph(value, boundary_tool)
    assert any('Parent.Parent(int)' in name for name in signatures(result))
    assert any('Work.Work(int)' in name for name in signatures(result))
    defaults = {node['signature']: node for node in result['nodes'] if node['kind'] == 'instance_field_default'}
    assert defaults['example.Work.text']['default_value'] == 'null'
    assert defaults['example.Work.number']['default_value'] == '0'
    assert defaults['example.Work.enabled']['default_value'] == 'false'
    assert defaults['example.Work.character']['default_value'] == '\\u0000'
    assert all(node['initialization_rule'] == 'java_default_value' for node in defaults.values())


def test_java_implicit_calls_and_library_callbacks_are_not_lost(boundary_tool):
    value = unit(sources=[
        source('resource', 'package example; public class Resource implements AutoCloseable { public void close() {} }'),
        source('cursor', 'package example; public class Cursor implements java.util.Iterator<String> { public boolean hasNext() { return false; } public String next() { return "value"; } }'),
        source('values', 'package example; public class Values implements Iterable<String> { public java.util.Iterator<String> iterator() { return new Cursor(); } }'),
        source('value', 'package example; public class Value { public String toString() { return "kept"; } }'),
        source('comparator', 'package example; public class Ordering implements java.util.Comparator<String> { public int compare(String left, String right) { return left.length()-right.length(); } }'),
        source('work', '''package example; public class Work {
            public int execute() throws Exception {
                try (Resource resource = new Resource()) {
                    int n = 0;
                    for (String value : new Values()) n += value.length();
                    java.util.Collections.sort(new java.util.ArrayList<String>(), new Ordering());
                    return ("prefix" + new Value()).length() + n;
                }
            }
        }''')])
    result = graph(value, boundary_tool)
    names = signatures(result)
    assert {'example.Resource.close()', 'example.Values.iterator()', 'example.Cursor.hasNext()',
            'example.Cursor.next()', 'example.Value.toString()', 'example.Ordering.compare(java.lang.String, java.lang.String)'} <= names
    assert {'implicit_resource_close', 'implicit_iterator', 'implicit_string_conversion', 'external_callback'} <= {
        edge['kind'] for edge in result['edges']}


def test_super_call_does_not_dispatch_to_child_override(boundary_tool):
    value = unit(sources=[
        source('base', 'package example; public class Base { protected int read() { return 1; } }'),
        source('work', 'package example; public class Work extends Base { public int execute() { return super.read(); } protected int read() { return 99; } }')])
    result = graph(value, boundary_tool)
    assert 'example.Base.read()' in signatures(result)
    assert 'example.Work.read()' not in signatures(result)


def test_generic_interface_override_is_not_lost(boundary_tool):
    value = unit(sources=[
        source('processor', 'package example; public interface Processor<T> { T apply(T value); }'),
        source('implementation', 'package example; public class Implementation implements Processor<String> { public String apply(String value) { return value; } }'),
        source('work', 'package example; public class Work { public int execute() { Processor<String> p = new Implementation(); return p.apply("value").length(); } }')])
    result = graph(value, boundary_tool)
    assert 'example.Implementation.apply(java.lang.String)' in signatures(result)
    assert any(edge['uncertain'] and 'Processor.apply' in edge['declared_target'] for edge in result['edges'])


def test_reflection_retains_bodies_and_remains_explicitly_unbounded(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() throws Exception { Class.forName("example.Hidden").getMethod("secret").invoke(null); return 0; }
    }'''), source('hidden', '''package example; public class Hidden {
        private int seed = 7;
        public static int secret() { return 7; }
        public int otherwiseUnused() { return seed; }
    }''')])
    result = graph(value, boundary_tool)
    assert 'example.Hidden.secret()' in signatures(result)
    assert 'example.Hidden.otherwiseUnused()' in signatures(result)
    edges = [edge for edge in result['edges'] if edge['kind'] == 'reflective_dispatch']
    assert edges and all(edge['uncertain'] and edge['unbounded'] and edge['candidates'] for edge in edges)
    assert result['status'] == 'verification_incomplete'


def test_unresolved_calls_keep_candidates_and_empty_candidate_edges(boundary_tool):
    value = unit(sources=[
        source('work', 'package example; public class Work { public int execute() { Missing.empty(); return Missing.lookup(); } }'),
        source('helper', 'package example; public class Helper { public static int lookup() { return 1; } }')])
    result = graph(value, boundary_tool)
    assert 'example.Helper.lookup()' in signatures(result)
    edges = {edge['declared_target']: edge for edge in result['edges'] if edge['kind'] == 'unresolved_call'}
    assert edges['lookup']['candidates']
    assert edges['empty']['candidates'] == []
    assert all(edge['unbounded'] for edge in edges.values())


def test_method_references_and_recursive_calls_are_finite_and_stable(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() { java.util.function.IntSupplier supplier = this::first; return supplier.getAsInt(); }
        private int first() { return second(); }
        private int second() { return first(); }
        public int unused() { return 99; }
    }''')])
    result = graph(value, boundary_tool)
    assert {'example.Work.first()', 'example.Work.second()'} <= signatures(result)
    assert 'example.Work.unused()' not in signatures(result)
    assert len({node['id'] for node in result['nodes']}) == len(result['nodes'])
    assert graph(value, boundary_tool) == result


def test_anonymous_bodies_are_retained_without_claiming_precise_binding(boundary_tool):
    value = unit(sources=[source('work', '''package example; public class Work {
        public int execute() { Runnable r = new Runnable() {
            public void run() { hidden(); }
            private void hidden() { System.out.println("value"); }
        }; r.run(); return 0; }
    }''')])
    result = graph(value, boundary_tool)
    assert any('private void hidden()' in node['excerpt'] for node in result['nodes'])
    assert any(edge['kind'] == 'local_type_binding' and edge['candidates'] for edge in result['edges'])
    assert result['status'] == 'verification_incomplete'


@pytest.mark.parametrize('change', ['hash', 'lines', 'candidate'])
def test_bad_graph_provenance_or_dangling_candidates_are_rejected(boundary_tool, change):
    from tools.behavior_verification.java_tool import analyze_entries
    value = unit()
    boundary = boundary_contract(value)
    analysis, _ = analyze_entries({boundary.source_manifest_hash: dict(sources=value['sources'], boundaries=[boundary])}, boundary_tool)
    element = deepcopy(analysis.find('entry/reachability'))
    if change == 'hash': element.find('code').set('source_hash', 'fabricated')
    elif change == 'lines': element.find('code').set('start_line', '9999')
    else: ElementTree.SubElement(element.find('edge'), 'candidate', id='outside-source')
    result = read_reachable_slice(element, boundary, {item['identity']: item for item in value['sources']}, {})
    assert result.status == 'verification_incomplete'
    assert result.issues and not result.nodes
