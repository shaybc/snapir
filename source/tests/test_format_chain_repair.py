"""Verify automatic implementation repair retains the original failing regression tests."""
import json
from types import SimpleNamespace
from models.pipeline_configuration import PipelineConfiguration
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_format_component_bundle import NativeFormatComponentBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.test_feedback import TestCorrectionError as ExecutedTestError
from runtime.java_toolchain import java_scope
from tests.runtime.test_behavior_conversion import state


def test_executed_value_failure_repairs_java_without_rewriting_tests(monkeypatch):
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *args:None)
    pkg='com.company.generated.automatic'
    path=lambda name:'src/main/java/'+pkg.replace('.','/')+'/'+name+'.java'
    basic='package '+pkg+'; public class Basic { public String format(String value){return value;} }'
    mapper='package '+pkg+'; public class Mapper { public String format(String value){return new '+pkg+'.Chain().format(value);} }'
    test_path='src/test/java/'+pkg.replace('.','/')+'/MapperTest.java'
    test_code='package '+pkg+'; public class MapperTest { public void empty(){ org.junit.jupiter.api.Assertions.assertEquals("", new '+pkg+'.Mapper().format("")); } }'
    call='String result = new '+pkg+'.Basic().format(value);'
    payload=dict(kind='format_composition',native_package=pkg,requirements={'r':'Keep empty values'},sources=[dict(identity='source',content='package original; public class Format { public String format(String value){return value;} }')],
        expected_contract_fields={'component':dict(component_id='component',source_entry_points=['original.format'],evidence_ids=['source'],dependencies=[],configuration_mode='specialized')},
        format_chains=[dict(occurrence_id='field',class_name='Chain',direction='format',attributes={},inactive_decorators=[],operations=[dict(kind='basic',component_id='basic')])],
        prerequisite_components=[dict(contracts={'basic':dict(apis=[dict(type_name=pkg+'.Basic',method_signatures=['public String format(String value)'])])})])
    calls=[];failed_tests=[]
    class Validator:
        stage_prerequisites={path('Basic'):basic}
        last=None
        def compile_implementation(self,bundle):return dict(build_passed=True)
        def __call__(self,bundle,cached=False):
            if not failed_tests:
                failed_tests.append(next(f.content for f in bundle.files if f.path==test_path))
                raise ExecutedTestError('expected empty but got null',dict(diagnostics=[dict(category='assertion_failure',expected_value='',actual_value='null')]))
            assert next(f.content for f in bundle.files if f.path==test_path)==failed_tests[0]
            self.last=dict(build_validation=dict(build_passed=True,tests_passed=True,test_count=1))
    def model(prompt,encoded):
        data=json.loads(encoded);title=data['schema']['title'];calls.append(title)
        if title=='NativeImplementation':
            number=calls.count(title)+1
            body='String result=value;' if number==1 else call
            body+='return result;' if number<3 else 'return result==null?"":result;'
            code='package '+pkg+'; public class Chain { public String format(String value){'+body+'} }'
            return NativeImplementation(files=[dict(path=path('Chain'),content=code),dict(path=path('Mapper'),content=mapper)]).model_dump_json()
        if title.endswith('Details'):return json.dumps(dict(component_details={}))
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=test_path,content=test_code)],coverage={'r':[test_path]}).model_dump_json()
    conn,config=state()
    try:
        profile=PipelineConfiguration(model_provider='mock',executable_verification={'mode':'conversion_checklist_v1','experimental_disable_facts':True})
        with java_scope(PipelineConfiguration(java_version=25)):
            bundle,_=generate(conn,config,profile,'component_generation','unit','unused',payload,NativeFormatComponentBundle,validator=Validator(),model_call=model)
        assert calls.count('NativeImplementation')==2
        assert calls.count('NativeTestBundle')==1
        assert next(f.content for f in bundle.files if f.path==test_path)==test_code
        assert conn.execute("SELECT attempts FROM staged_conversion_tasks WHERE identity='unit' AND stage='tests'").fetchone()[0]==1
    finally:conn.close()
