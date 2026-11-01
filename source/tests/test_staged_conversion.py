"""Check parser metadata and focused stage ownership without claiming fixture receipts are equivalence."""
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_verification_binding import NativeVerificationBinding
from models.native_unit_bundle import NativeSourceFile,NativeUnitBundle
from runtime.behavior_conversion.native_metadata import inspect_native,resolve_dependencies
from runtime.behavior_conversion.native_binding_builder import build_binding,validate_parsed_binding,BindingAmbiguous
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from runtime.java_toolchain import java_scope
from tools.behavior_verification.java_tool import default_tool_path
from tests.runtime.test_behavior_conversion import state

PACKAGE='com.company.generated.staged'
MAIN='''package com.company.generated.staged;
public class Formatter { public String format(String value) { return value; } }
'''
ORIGINAL='''package legacy;
public class Original { public Object format(Context c) {return c.getValueAt("Value");} }
'''


@pytest.fixture(autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):
        yield


def files(text=MAIN,name='Formatter'):
    return [NativeSourceFile(path='src/main/java/'+PACKAGE.replace('.','/')+'/'+name+'.java',content=text)]


def unit():
    return dict(unit_id='unit',kind='response_format',fingerprint='original',configuration_xml='<fmtDef id="F"/>',
        effective_configuration=dict(attributes={'dataName':'Value'},children=[]),referenced_definitions=[])


def payload():
    return dict(kind='thin_path_experiment',selected_unit=unit(),sources=[dict(identity='original',content=ORIGINAL)],
        requirements={'observed':'Preserve original boundary'},known_dependencies=[],runtime_controls=[])


def test_parser_reads_real_methods_constructors_nested_types_and_original_keys():
    text='''package com.company.generated.staged; import java.util.Set;
    public class Formatter {
      // public String fake() { return "not code"; }
      public String format(String value) { return value; }
      public static void configure(Set<String> channels) {}
      public static class Values { private String value; public String getValue(){return value;}
        public void setValue(String value){this.value=value;} }
      private static class Hidden { public void invisible(){} }
    }'''
    metadata=inspect_native(files(text),original_sources=payload()['sources'])
    assert PACKAGE+'.Formatter.Values' in metadata['types']
    assert PACKAGE+'.Formatter.Hidden' not in metadata['types']
    methods=metadata['types'][PACKAGE+'.Formatter']['methods']
    assert [m['name'] for m in methods]==['format','configure']
    assert methods[1]['parameters'][0]['type']=='java.util.Set'
    assert metadata['context_keys']==[dict(name='Value',source='original',method='getValueAt')]


def test_binding_uses_parsed_setter_and_settings_shapes_without_model_call():
    text='''package com.company.generated.staged; import java.util.Set;
    public class Formatter {
      public String format(Values reply) { return reply.getValue(); }
      public static void configure(Set<String> channels,Set<String> exclusions){}
      public static class Values { private String value; public String getValue(){return value;}
        public void setValue(String value){this.value=value;} }
    }'''
    sources=[*payload()['sources'],dict(identity='settings',content='''package legacy; import java.util.Set;
      public class Settings {public static void configure(Set<String> a,Set<String> b) {}}''')]
    metadata=inspect_native(files(text),original_sources=sources)
    binding=build_binding(unit(),metadata,[dict(target='legacy.Settings.configure',arity=2)])
    assert list(binding.arguments[0].properties)==['setValue']
    assert binding.settings_bindings=={'legacy.Settings.configure':{'class':PACKAGE+'.Formatter','method':'configure'}}
    invalid=binding.model_copy(deep=True)
    invalid.arguments[0].properties={'value':next(iter(binding.arguments[0].properties.values()))}
    with pytest.raises(ValueError,match='parsed method'):validate_parsed_binding(invalid,metadata,[dict(target='legacy.Settings.configure')])


def test_wrong_settings_shapes_fail_schema_with_explicit_required_names():
    with pytest.raises(ValidationError):NativeVerificationBinding(owner_type='T',method_name='format',
        settings_bindings={'original':{'target':'native.Type.configure'}})
    schema=NativeVerificationBinding.model_json_schema()
    target=schema['$defs']['NativeSettingsBinding']
    assert set(target['required'])=={'class','method'} and target['additionalProperties'] is False


def test_dependency_resolution_never_invents_or_changes_coordinates():
    metadata=dict(types={},imports=[dict(name='library.api.Value',static='false',wildcard='false')])
    known=[dict(group_id='library.api',artifact_id='library',version='1',scope='compile',reason='approved')]
    resolved,unknown=resolve_dependencies(metadata,known)
    assert not unknown and resolved[0].version=='1'
    # A group-prefix inventory candidate is not a claim that the class is owned by its direct JAR.
    # Actual compilation must establish availability (including umbrella/transitive dependencies).
    assert resolved[0].required_classes==[]
    assert resolve_dependencies(metadata,[])[1]==['library.api.Value']
    with pytest.raises(ValueError,match='pinned'):resolve_dependencies(metadata,known,[dict(known[0],version='2')])


class FlowValidator:
    """Mock technical receipts exercise orchestration only; parser subprocesses remain real."""
    tool=default_tool_path()
    def __init__(self,difference=False):self.compiles=0;self.accepted=0;self.difference=difference
    def fresh(self):pass
    def compile_implementation(self,bundle):self.compiles+=1;return dict(build_passed=True)
    def __call__(self,bundle,cached=False):
        self.accepted+=1
        self.last=dict(build_validation=dict(build_passed=True,tests_passed=True,test_count=1),fixture_only=True)
        if self.difference and self.accepted==1:
            raise VerificationFailure(dict(stage='thin_path_boundary',failing_cases=[dict(input='x',expected='x',actual='bad')]))


def test_focused_calls_return_only_code_then_tests_with_parser_built_contract():
    conn,config=state();validator=FlowValidator();calls=[]
    def model(prompt,encoded):
        request=json.loads(encoded);schema=request['schema']['title'];calls.append(schema)
        if schema=='NativeImplementation':
            assert 'testing_contract' not in request and 'coverage_example' not in request and 'requirements' not in request
            return NativeImplementation(files=files()).model_dump_json()
        assert schema=='NativeTestBundle'
        assert 'original_sources' in request and 'parsed_apis' in request
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        result,_=generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused bundled instructions',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeTestBundle']
        assert result.verification_binding.arguments[0].key=='Value'
        assert result.unit_contract.apis[0].type_name==PACKAGE+'.Formatter'
        assert validator.compiles==validator.accepted==1
    finally:conn.close()


def test_production_difference_returns_to_implementation_without_burning_test_retries():
    conn,config=state();validator=FlowValidator(difference=True);calls=[]
    def model(prompt,encoded):
        request=json.loads(encoded);kind=request['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeTestBundle','NativeImplementation']
        assert dict(conn.execute('SELECT stage,attempts FROM staged_conversion_tasks').fetchall())['tests']==1
    finally:conn.close()


def test_tests_cannot_edit_production_and_do_not_reset_their_budget():
    conn,config=state();validator=FlowValidator();calls=[]
    def model(prompt,encoded):
        kind=json.loads(encoded)['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        return NativeTestBundle(files=files(),coverage={}).model_dump_json()
    try:
        profile=PipelineConfiguration(model_provider='mock',staged_unit_conversion=True)
        for _ in range(2):
            with pytest.raises(ValueError):generate(conn,config,profile,'thin_path_experiment','unit','unused',payload(),
                NativeUnitBundle,validator=validator,model_call=model)
        assert calls.count('NativeImplementation')==1 and calls.count('NativeTestBundle')==4
        assert validator.accepted==0
    finally:conn.close()


def test_ambiguous_mapping_uses_small_mapping_only_call_and_validates_choices():
    conn,config=state();validator=FlowValidator();calls=[]
    def model(prompt,encoded):
        request=json.loads(encoded);kind=request['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files(MAIN.replace('String value','String unnamed').replace('return value','return unnamed'))).model_dump_json()
        if kind=='NativeMappingSelection':
            assert 'sources' not in request and 'production_files' not in request
            return json.dumps(dict(binding=dict(owner_type=PACKAGE+'.Formatter',method_name='format',
                arguments=[dict(type_name='java.lang.String',source='context',key='Value')],output='result')))
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeMappingSelection','NativeTestBundle']
    finally:conn.close()


def test_comparison_limitation_does_not_request_replacement_code_or_tests():
    conn,config=state();validator=FlowValidator();calls=[]
    def incomplete(*args,**kwargs):raise VerificationIncomplete(dict(stage='comparison',issues=['presence not observable']))
    validator.__class__=type('IncompleteFlow',(FlowValidator,),{'__call__':incomplete})
    def model(prompt,encoded):
        kind=json.loads(encoded)['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        with pytest.raises(VerificationIncomplete):generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeTestBundle']
    finally:conn.close()


def test_side_road_uses_the_same_separate_code_and_test_stages():
    conn,config=state();calls=[]
    class SideValidator(FlowValidator):
        def side_road_validate(self,bundle,stage):
            return dict(status='matched_observed_cases',observed_cases=1,
                build_validation=dict(build_passed=True,tests_passed=True))
    validator=SideValidator()
    def model(prompt,encoded):
        request=json.loads(encoded);kind=request['schema']['title'];phase=request.get('conversion_phase')
        calls.append((kind,phase))
        if kind=='NativeImplementation':
            source=MAIN if phase!='native' else MAIN.replace('public class','import com.ibm.dse.base.Context; public class')
            return NativeImplementation(files=files(source)).model_dump_json()
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True,side_road_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls.count(('NativeImplementation','native'))==4
        assert ('NativeImplementation','baseline') in calls and ('NativeImplementation','simplify') in calls
        assert calls.count(('NativeTestBundle',None))==2
        row=conn.execute('SELECT baseline_attempts,simplify_attempts,status FROM side_road_conversions').fetchone()
        assert tuple(row)==(1,1,'simplified_verified')
    finally:conn.close()


@pytest.mark.parametrize('bad_getter',[False,True])
def test_helpers_are_allowed_and_selected_accessor_errors_return_to_implementation(bad_getter):
    conn,config=state();validator=FlowValidator();calls=[];implementations=0
    def model(prompt,encoded):
        nonlocal implementations
        request=json.loads(encoded);kind=request['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':
            implementations+=1
            getter='Object' if bad_getter and implementations==1 else 'String'
            if implementations>1:assert request['implementation_feedback']['stage']=='typed_boundary'
            source='''package com.company.generated.staged;
            public class Formatter {
              public String format(Values reply){return String.valueOf(reply.getValue());}
              public java.util.Map<String,Object> helper(){return java.util.Map.of();}
              public static class Values {
                private String value;
                public GETTER getValue(){return value;}
                public void setValue(String value){this.value=value;}
                public static Values fromMap(java.util.Map<String,?> values){return new Values();}
              }
            }'''.replace('GETTER',getter)
            return NativeImplementation(files=files(source)).model_dump_json()
        assert kind=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==(['NativeImplementation']*(2 if bad_getter else 1))+['NativeTestBundle']
        assert validator.accepted==1
    finally:conn.close()


def test_selected_direction_ignores_comments_and_other_helper_receivers():
    from runtime.behavior_conversion.native_test_scope import test_scope as scope_for, validate_test_scope
    binding=NativeVerificationBinding(owner_type=PACKAGE+'.Formatter',method_name='format')
    scope=scope_for(unit(),binding,[])
    text='package com.company.generated.staged;\n    public class FormatterTest {\n      Formatter formatter=new Formatter(); Other other=new Other();\n      void check() {\n        // formatter.unformat("comment");\n        String text="formatter.unformat(fake)";\n        formatter.format("ok"); other.unformat("ok");\n      }\n    }'
    validate_test_scope(inspect_native(files(text,'FormatterTest')),scope)
    invalid=text.replace('formatter.format("ok")','formatter.unformat("ok")')
    with pytest.raises(ValueError,match='outside selected boundary'):
        validate_test_scope(inspect_native(files(invalid,'FormatterTest')),scope)


def test_junit_failure_retries_tests_without_regenerating_production():
    from runtime.behavior_conversion.test_feedback import TestCorrectionError
    class Validator(FlowValidator):
        def __call__(self,bundle,cached=False):
            self.accepted+=1
            if self.accepted==1:
                raise TestCorrectionError('JUnit assertion failed',dict(diagnostics=[dict(message='expected original value')],failed_sources=[]))
    conn,config=state();validator=Validator();calls=[]
    def model(prompt,encoded):
        request=json.loads(encoded);kind=request['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        assert request['selected_boundary']['method_name']=='format'
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls==['NativeImplementation','NativeTestBundle','NativeTestBundle']
    finally:conn.close()


def test_exhausted_test_budget_does_not_block_revalidation_after_code_correction():
    conn,config=state();validator=FlowValidator(difference=True);calls=[];test_calls=0
    def model(prompt,encoded):
        nonlocal test_calls
        kind=json.loads(encoded)['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        test_calls+=1
        if test_calls<4:return NativeTestBundle(files=files(),coverage={}).model_dump_json()
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert test_calls==4 and calls.count('NativeImplementation')==2
        assert validator.accepted==2  # Both candidates rerun validation; the old pass is never acceptance.
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='tests'").fetchone()[0]==4
        row=conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE stage='passing_tests'").fetchone()
        retained=json.loads(row[0])
        assert retained['validation']['test_count']==1 and retained['accepted'] is False
        assert retained['context']['binding']['method_name']=='format'
    finally:conn.close()


def test_retained_tests_are_source_policy_bound_and_hash_checked():
    from tools.state_store_tools import staged_conversion_state as store
    from tools.component_inventory_tools.identity import stable_id
    conn,config=state()
    tests={'files':[],'coverage':{}}
    context=dict(revision='source-revision',eligibility_hash='policy',production_hash='production',selected_boundary={})
    try:
        assert not store.retain_passing_tests(conn,config.run_id,'unit','source-revision',tests,context,
            dict(build_passed=True,tests_passed=True,test_count=0))
        assert store.passing_tests(conn,config.run_id,'unit','source-revision','policy') is None
        assert store.retain_passing_tests(conn,config.run_id,'unit','source-revision',tests,context,
            dict(build_passed=True,tests_passed=True,test_count=1))
        assert store.passing_tests(conn,config.run_id,'unit','new-source-revision','policy') is None
        assert store.passing_tests(conn,config.run_id,'unit','source-revision','new-policy') is None
        kept=store.passing_tests(conn,config.run_id,'unit','source-revision','policy')
        assert kept['test_hash']==stable_id(tests)
        kept['tests']['coverage']={'tampered':['changed.java']}
        conn.execute("UPDATE staged_conversion_tasks SET artifact_json=? WHERE stage='passing_tests' AND revision='source-revision'",(json.dumps(kept),))
        with pytest.raises(ValueError,match='integrity'):store.passing_tests(conn,config.run_id,'unit','source-revision','policy')
    finally:conn.close()


@pytest.mark.parametrize('limitation',[False,True])
def test_revalidation_failure_is_not_old_acceptance_or_unlimited_test_retries(limitation):
    class Validator(FlowValidator):
        def __call__(self,bundle,cached=False):
            if self.accepted:
                self.accepted+=1
                if limitation:raise VerificationIncomplete(dict(stage='comparison',issues=['JVM unavailable']))
                from runtime.behavior_conversion.test_feedback import TestCorrectionError
                raise TestCorrectionError('assertion failed against changed code',dict(diagnostics=[dict(message='expected x')],failed_sources=[]))
            return super().__call__(bundle,cached)
    conn,config=state();validator=Validator(difference=True);calls=[]
    def model(prompt,encoded):
        kind=json.loads(encoded)['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':return NativeImplementation(files=files()).model_dump_json()
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        with pytest.raises(VerificationIncomplete if limitation else ValueError):
            generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
                'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert calls.count('NativeTestBundle')==(1 if limitation else 4)
        assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='thin_path_experiment' AND status='accepted'").fetchone()[0]==0
    finally:conn.close()


def test_changed_selected_api_repairs_retained_tests_with_remaining_budget():
    conn,config=state();validator=FlowValidator(difference=True);calls=[];implementations=0;tests=0
    def model(prompt,encoded):
        nonlocal implementations,tests
        request=json.loads(encoded);kind=request['schema']['title'];calls.append(kind)
        if kind=='NativeImplementation':
            implementations+=1
            text=MAIN if implementations==1 else MAIN.replace('format(', 'serialize(')
            return NativeImplementation(files=files(text)).model_dump_json()
        tests+=1
        if tests==2:
            assert request['retained_test_bundle']['files']
            assert 'Selected API changed' in request['retained_test_revalidation_error']
            assert request['selected_boundary']['method_name']=='serialize'
        return NativeTestBundle(files=[dict(path='src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java',
            content='package '+PACKAGE+'; public class FormatterTest {}')],coverage={'observed':[
                'src/test/java/'+PACKAGE.replace('.','/')+'/FormatterTest.java']}).model_dump_json()
    try:
        generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=True),
            'thin_path_experiment','unit','unused',payload(),NativeUnitBundle,validator=validator,model_call=model)
        assert tests==2 and validator.accepted==2
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE stage='tests'").fetchone()[0]==2
    finally:conn.close()
