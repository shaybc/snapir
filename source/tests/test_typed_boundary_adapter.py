"""Trusted typed bridge executes actual public APIs, never AI-supplied harness source."""
from copy import deepcopy
from pathlib import Path
import pytest
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.unit_verification_boundary import UnitVerificationBoundary
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.boundary_verification import verify_boundary
from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first


ROOT = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'


def typed_example(tool):
    original = unit(sources=[source('context', (ROOT / 'com/ibm/dse/base/Context.java').read_text()),
        source('work', '''package example; import com.ibm.dse.base.Context; public class Work {
        private Context context; public void setContext(Context context) { this.context=context; }
        public int execute() { String value=(String)context.getValueAt("value"); context.setValueAt("result", value); return 0; }
    }''')])
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original), tool_jar=tool)))
    native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter', sources=[dict(
        path='nativefixture/Work.java', content='''package nativefixture; public class Work {
        public Result execute(String value) { return new Result(value); }
        public static class Result { private final String value; public Result(String value){this.value=value;}
        public String getValue(){return value;} public int getCode(){return 0;} }
    }''')], native_entry=dict(owner_type='nativefixture.Work', method_name='execute',
        arguments=[dict(type_name='java.lang.String', source='context', key='value')],
        context_writes=[dict(context_key='result', getters=['getValue'])], output_getters=['getCode']))
    legacy = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
    return original, boundary, legacy, native


def test_actual_typed_result_and_ordered_context_write_are_compared(boundary_tool, tmp_path):
    original, boundary, legacy, native = typed_example(boundary_tool)
    cases = [BoundaryCase(case_id='null', initial_context={'value': None}),
             BoundaryCase(case_id='text', initial_context={'value': 'hello'})]
    report = verify_boundary(original, boundary, legacy, native, cases, tmp_path / 'typed', tool=boundary_tool,
                             candidate_label='typed_api_test_fixture')
    assert report.status == 'matched_observed_cases', report.model_dump_json(indent=2)
    assert report.cases[1]['native']['context']['result'] == 'hello'
    assert report.cases[1]['native']['writes']
    native.sources[0].content = native.sources[0].content.replace('return value;', 'return "invented";')
    changed = verify_boundary(original, boundary, legacy, native, cases, tmp_path / 'changed', tool=boundary_tool,
                              candidate_label='typed_api_deliberate_defect')
    assert changed.status == 'differences_found', changed.model_dump_json(indent=2)


def test_projection_cannot_invoke_unrelated_jdk_methods(boundary_tool, tmp_path):
    original, boundary, legacy, native = typed_example(boundary_tool)
    native.native_entry.context_writes[0].getters = ['getClass', 'getClassLoader']
    report = verify_boundary(original, boundary, legacy, native, [BoundaryCase(case_id='unsafe')],
        tmp_path / 'unsafe', tool=boundary_tool, candidate_label='invalid_metadata_fixture')
    assert report.status == 'verification_incomplete'


@pytest.mark.parametrize('file_input', [False, True])
def test_jackson_string_codec_is_supported_but_file_overload_is_not(boundary_tool, tmp_path, file_input):
    repository = Path.home() / '.m2/repository'
    coordinates = [(f'com/fasterxml/jackson/core/{name}', '2.17.2', name) for name in
                   ('jackson-core','jackson-annotations','jackson-databind')]
    coordinates += [('com/fasterxml/jackson/dataformat/jackson-dataformat-xml','2.17.2','jackson-dataformat-xml'),
                    ('org/codehaus/woodstox/stax2-api','4.2.2','stax2-api'),
                    ('com/fasterxml/woodstox/woodstox-core','6.7.0','woodstox-core')]
    jars = [repository / group / version / (artifact+'-'+version+'.jar') for group,version,artifact in coordinates]
    assert all(jar.is_file() for jar in jars), 'Populate the pinned native XML fixture dependencies before offline testing'
    original = unit('response_format', 'example.Formatter', sources=[source('context', (ROOT/'com/ibm/dse/base/Context.java').read_text()),
        source('formatter', '''package example; import com.ibm.dse.base.Context; public class Formatter {
            public String format(Context context) { String value=(String)context.getValueAt("value");
                return value == null ? "<R><value/></R>" : "<R><value>"+value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")+"</value></R>"; }
        }''')])
    original['effective_configuration']['children'][0]['decorators'] = []
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original), tool_jar=boundary_tool)))
    body = ('return new XmlMapper().readValue(new java.io.File(value), Wire.class).value;' if file_input else
            'Wire wire=new Wire(); wire.value=value; return new XmlMapper().writeValueAsString(wire);')
    native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
        native_entry=dict(owner_type='nativefixture.Formatter',method_name='render',arguments=[dict(type_name='java.lang.String',source='context',key='value')]),
        classpath=list(map(str,jars)), sources=[dict(path='nativefixture/Formatter.java', content='''package nativefixture;
            import com.fasterxml.jackson.dataformat.xml.XmlMapper;
            import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
            public class Formatter { public String render(String value) throws Exception { BODY }
            @JacksonXmlRootElement(localName="R") public static class Wire { public String value; } }
        '''.replace('BODY',body))])
    report = verify_boundary(original,boundary,BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'),
        native,[BoundaryCase(case_id='value',initial_context={'value':'hello'}),BoundaryCase(case_id='null',initial_context={'value':None})],
        tmp_path/'codec',tool=boundary_tool,candidate_label='native_codec_test_fixture')
    assert report.status == ('verification_incomplete' if file_input else 'matched_observed_cases'), report.model_dump_json(indent=2)
    if file_input:
        assert any('Uncontrolled external dependency' in issue for issue in report.issues)
        assert not report.cases
