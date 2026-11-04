"""Real JVM execution for shared data, typed collections, JDBC and whole-step comparison."""
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeSourceFile
from runtime.java_toolchain import java_scope,run_java
from runtime.test_assets.store import publish
from runtime.test_assets.materialization import comparison_plan
from runtime.test_assets.junit_support import check_execution
from runtime.format_comparison.runner import run_comparison
from runtime.step_comparison.runner import run_step_comparison
from runtime.format_comparison.planning import original_unit
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from test_behavior_verification_boundaries import source,unit
from test_format_comparison_execution import demo_sources


@pytest.fixture(scope='module',autouse=True)
def jdk():
    with java_scope(PipelineConfiguration(java_version=25)):yield


@pytest.fixture(scope='module')
def boundary_tool(tmp_path_factory):
    """Build this runtime in isolation; active pilots keep their own immutable harness JAR."""
    from tools.maven_dependency_tools.command import maven_executable
    original=Path(__file__).resolve().parents[1]/'behavior-verification-java'
    staged=tmp_path_factory.mktemp('shared-fixture-tool')
    shutil.copy2(original/'pom.xml',staged/'pom.xml');shutil.copytree(original/'src',staged/'src')
    result=run_java([maven_executable(),'-q','--offline','-f',str(staged/'pom.xml'),'package'],capture_output=True,text=True,timeout=180,check=False)
    assert result.returncode==0,result.stderr+result.stdout
    return staged/'target/behavior-verification-1.0.0-jar-with-dependencies.jar'


def test_fixture_runtime_constructs_typed_lists_and_jdbc_and_isolates_inputs(boundary_tool,tmp_path):
    code='''package nativecode; import java.sql.*;import java.util.*;
public class Sample {
 public String join(List<Row> rows) {String text=rows.get(0).getName();rows.clear();return text;}
 public String lookup(Connection c,String key)throws Exception {try(var p=c.prepareStatement("SELECT V FROM T WHERE K = ?")){p.setString(1,key);try(var r=p.executeQuery()){return r.next()?r.getString(1):"empty";}}}
 public String unsupported(Connection c)throws Exception {c.getMetaData();return "wrong";}
 public String swallowed(Connection c){try{c.getMetaData();}catch(Exception ignored){}return "wrong";}
 public String wrongColumn(Connection c)throws Exception {try(var p=c.prepareStatement("SELECT V FROM T WHERE K = ?")){p.setString(1,"k");try(var r=p.executeQuery()){r.next();return r.getString("MISSING");}}}
 public boolean wrongType(Connection c)throws Exception {try(var p=c.prepareStatement("SELECT V FROM T WHERE K = ?")){p.setString(1,"k");try(var r=p.executeQuery()){r.next();return r.getBoolean(1);}}}
 public String decimal(java.math.BigDecimal number){return number.toPlainString();}
}'''
    row='package nativecode;public class Row {private String name;public Row(String name){this.name=name;}public String getName(){return name;}}'
    recipes=dict(type_name='java.util.List',source='collection',key='rows',element=dict(type_name='nativecode.Row',source='object',
        arguments=[dict(type_name='java.lang.String',source='item',key='/name')]))
    bank=SharedFixtureBank(fixtures={'rows':dict(value=[{'name':'one'}]),'key':dict(value='k'),
        'db':dict(kind='database',value={'queries':[dict(sql='SELECT V FROM T WHERE K = ?',parameters=['k'],columns=['V'],rows=[['found']])]}),
        'nil':dict(value=None),'decimal':dict(value={'$decimal':'123456789.123450'})})
    scenarios=[dict(scenario_id='small_collection',purpose='Row mapping and mutation',native_entry=dict(owner_type='nativecode.Sample',method_name='join',arguments=[recipes]),
        inputs={'rows':dict(fixture_id='rows')},assertions=['Returns one']),
        dict(scenario_id='lookup',purpose='Database lookup',native_entry=dict(owner_type='nativecode.Sample',method_name='lookup',arguments=[dict(type_name='java.sql.Connection',source='resource',key='db'),dict(type_name='java.lang.String',source='fixture',key='key')]),inputs={'key':dict(fixture_id='key')},resources={'db':dict(fixture_id='db')},assertions=['Returns found']),
        dict(scenario_id='unsupported',purpose='Missing JDBC capability',native_entry=dict(owner_type='nativecode.Sample',method_name='unsupported',arguments=[dict(type_name='java.sql.Connection',source='resource',key='db')]),resources={'db':dict(fixture_id='db')},assertions=['Must remain unavailable'])]
    scenarios.extend([dict(scenario_id='swallowed',purpose='Caught adapter failure stays incomplete',native_entry=dict(owner_type='nativecode.Sample',method_name='swallowed',arguments=[dict(type_name='java.sql.Connection',source='resource',key='db')]),resources={'db':dict(fixture_id='db')},assertions=['Must remain unavailable']),
        dict(scenario_id='decimal',purpose='Lossless logical decimals',native_entry=dict(owner_type='nativecode.Sample',method_name='decimal',arguments=[dict(type_name='java.math.BigDecimal',source='fixture',key='number')]),inputs={'number':dict(fixture_id='decimal')},assertions=['Retains decimal scale']),
        dict(scenario_id='constructor',purpose='Construct one row',entry_kind='constructor',native_entry=dict(owner_type='nativecode.Row',method_name='<init>',constructor_arguments=[dict(type_name='java.lang.String',source='fixture',key='key')]),inputs={'key':dict(fixture_id='key')},assertions=['Retains constructor value'])])
    for method in ['wrongColumn','wrongType']:
        scenarios.append(dict(scenario_id=method,purpose='Missing/unsupported fixture data remains incomplete',native_entry=dict(owner_type='nativecode.Sample',method_name=method,arguments=[dict(type_name='java.sql.Connection',source='resource',key='db')]),resources={'db':dict(fixture_id='db')},assertions=['Must remain unavailable']))
    root,manifest=publish(tmp_path/'assets','sample',{},bank,JunitScenarioSuite(scenarios=scenarios),ComparisonScenarioSuite())
    h=digest(manifest.model_dump(mode='json'))
    driver='''import il.co.dcd.verification.fixtures.*;
public class Driver { public static void main(String[] a)throws Exception {var s=FixtureStore.open(a[0],a[1]);
if(!"one".equals(s.run("small_collection").value())||!"one".equals(s.run("small_collection").value()))throw new AssertionError("mutation leak");
if(!"found".equals(s.run("lookup").value()))throw new AssertionError("JDBC");
try{s.run("unsupported");throw new AssertionError("unsupported operation hidden");}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}
try{s.run("swallowed");throw new AssertionError("caught capability failure hidden");}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}
if(!"123456789.123450".equals(s.run("decimal").value()))throw new AssertionError("decimal changed");
if(!"k".equals(((nativecode.Row)s.run("constructor").value()).getName()))throw new AssertionError("constructor");
for(String id:new String[]{"wrongColumn","wrongType"})try{s.run(id);throw new AssertionError("invalid fixture hidden");}catch(il.co.dcd.verification.harness.BoundaryRuntime.Incomplete expected){}
}}'''
    paths=[]
    for name,text in [('Sample.java',code),('Row.java',row),('Driver.java',driver)]:
        p=tmp_path/name;p.write_text(text);paths.append(str(p))
    classes=tmp_path/'classes';classes.mkdir()
    compiled=run_java(['javac','-cp',str(boundary_tool),'-d',str(classes),*paths],capture_output=True,text=True,timeout=60,check=False)
    assert compiled.returncode==0,compiled.stderr
    execution=run_java(['java','-ea','-cp',os.pathsep.join([str(classes),str(boundary_tool)]),'Driver',str(root),h],cwd=tmp_path,capture_output=True,text=True,timeout=60,check=False)
    assert execution.returncode==0,execution.stderr
    records=[json.loads(line) for line in (tmp_path/'target/shared-fixture-executions.jsonl').read_text().splitlines()]
    assert len(records)==5 and all(r['manifest_hash']==h for r in records)


def test_native_context_named_dto_runs_in_junit_and_comparison(boundary_tool,tmp_path):
    native='''package nativecode;public class Sample {
public String format(ExampleContext input){return "<v>"+input.getValue()+"</v>";}}'''
    dto='''package nativecode;public class ExampleContext {private final String value;
public ExampleContext(String value){this.value=value;}public String getValue(){return value;}}'''
    recipe=dict(type_name='nativecode.ExampleContext',source='object',arguments=[dict(type_name='java.lang.String',source='fixture',key='value')])
    binding=dict(owner_type='nativecode.Sample',method_name='format',arguments=[recipe])
    bank=SharedFixtureBank(fixtures={'value':dict(value='demo')})
    junit=JunitScenarioSuite(scenarios=[dict(scenario_id='dto',purpose='Accept an owned typed context DTO',native_entry=binding,
        inputs={'value':dict(fixture_id='value')},assertions=['Formats the supplied DTO value'])])
    root,manifest=publish(tmp_path/'assets','dto',{},bank,junit,ComparisonScenarioSuite())
    h=digest(manifest.model_dump(mode='json'))
    driver='''import il.co.dcd.verification.fixtures.*;public class Driver {
public static void main(String[] args)throws Exception {
if(!"<v>demo</v>".equals(FixtureStore.open(args[0],args[1]).run("dto").value()))throw new AssertionError();}}'''
    paths=[]
    for name,text in [('Sample.java',native),('ExampleContext.java',dto),('Driver.java',driver)]:
        path=tmp_path/name;path.write_text(text);paths.append(str(path))
    classes=tmp_path/'classes';classes.mkdir()
    compiled=run_java(['javac','-cp',str(boundary_tool),'-d',str(classes),*paths],capture_output=True,text=True,timeout=60,check=False)
    assert compiled.returncode==0,compiled.stderr
    execution=run_java(['java','-ea','-cp',os.pathsep.join([str(classes),str(boundary_tool)]),'Driver',str(root),h],cwd=tmp_path,capture_output=True,text=True,timeout=60,check=False)
    assert execution.returncode==0,execution.stderr
    original='''package example;import com.ibm.dse.base.*;public class Format {
public void initializeFrom(Tag tag){}public String format(Context context){return "<v>"+context.getValueAt("Value")+"</v>";}}'''
    configured=original_unit([*demo_sources(),source('format',original)],dict(java_class='example.Format',attributes={}))
    suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='whole',purpose='Pass the same value through different context types',
        direction='format',native_entry=binding,inputs={'value':dict(fixture_id='value')},composer_context={'Value':dict(fixture_id='value')})])
    files=[NativeSourceFile(path='src/main/java/nativecode/Sample.java',content=native),NativeSourceFile(path='src/main/java/nativecode/ExampleContext.java',content=dto)]
    plan=comparison_plan('dto',configured,files,bank,suite,'dto-fixtures')
    result=run_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'comparison',tool=boundary_tool)
    assert result['counts']['matched']==1,result


def test_same_fixture_drives_boolean_format_and_unformat(boundary_tool,tmp_path):
    repo=Path(__file__).resolve().parents[2];original=repo/'bank-demo/composer/Workspace/WSBCC_XML/src'
    native=repo/'outputs/getclientlinks-dependency-alignment-20261103/single-get-client-links/generated/components/7eac14be1092f608-3a8da1719fca/src/main/java/com/company/generated/components/c622aebaba4903b67/CCBoolean.java'
    if not native.exists():pytest.skip('Saved-candidate pilot requires the retained local conversion output')
    sources=[*demo_sources(),source('boolean',next(original.rglob('CCBoolean.java')).read_bytes().decode())]
    original_format=original_unit(sources,dict(java_class='com.ibm.il.dse.cc.format.CCBoolean',attributes={'dataName':'Flag'}))
    owner='com.company.generated.components.c622aebaba4903b67.CCBoolean'
    bank=SharedFixtureBank(fixtures={'flag':dict(value=True),'xml':dict(kind='xml',value='<Flag>true</Flag>')})
    common=dict(owner_type=owner,constructor_arguments=[dict(type_name='java.lang.String',source='configuration',key='dataName')])
    comparisons=ComparisonScenarioSuite(scenarios=[dict(scenario_id='whole_format',purpose='Complete boolean field',direction='format',native_entry=dict(common,method_name='format',arguments=[dict(type_name='java.lang.Boolean',source='fixture',key='flag')]),inputs={'flag':dict(fixture_id='flag')},composer_context={'Flag':dict(fixture_id='flag')}),
        dict(scenario_id='whole_unformat',purpose='Complete parse',direction='unformat',input_xml=dict(fixture_id='xml'),native_entry=dict(common,method_name='unformat',arguments=[dict(type_name='java.lang.String',source='xml')],context_writes=[dict(context_key='Flag',source='result')]))])
    plan=comparison_plan('saved-boolean',original_format,[NativeSourceFile(path='src/main/java/'+owner.replace('.','/')+'.java',content=native.read_bytes().decode())],bank,comparisons,'pilot-manifest')
    profile=PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False})
    report=run_comparison(plan,profile,tmp_path/'comparison',tool=boundary_tool)
    assert report['status']=='completed' and report['counts']['matched']==2,report
    assert report['fixture_manifest_hash']=='pilot-manifest' and report['inputs_unchanged']


def test_whole_step_uses_same_external_response_and_reports_context(boundary_tool,tmp_path):
    original='''package example;import com.ibm.dse.base.Context;
public class Step {private Context context; public void setContext(Context c){context=c;}
public int execute(){context.setValueAt("Answer",Client.call((String)context.getValueAt("Input")));return 1;}}'''
    native='''package nativecode;public class Step {private String answer;public int execute(String input){answer=input;return 1;}public String getAnswer(){return answer;}}'''
    client='package example;public class Client {public static String call(String input){throw new IllegalStateException("not replayed");}}'
    step=unit('configured_step','example.Step',sources=[*demo_sources(),source('step',original),source('client',client)])
    bank=SharedFixtureBank(fixtures={'input':dict(value='value'),'response':dict(kind='service',value=[dict(target='service:call',arguments=['value'],value='response')])})
    suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='whole_step',purpose='Return and output state',direction='step_execute',
        inputs={'input':dict(fixture_id='input')},composer_context={'Input':dict(fixture_id='input')},observe_context_keys=['Answer'],external_responses=dict(fixture_id='response'),
        native_entry=dict(owner_type='nativecode.Step',method_name='execute',arguments=[dict(type_name='java.lang.String',source='fixture',key='input')]))])
    # This class exposes output on its receiver, which the current binding cannot project.
    # Use a supported result-bearing argument to avoid inventing a receiver-state mapping.
    native='''package nativecode;public class Step {public int execute(Value value){value.setAnswer(Client.call(value.getInput()));return 1;}}'''
    dto='''package nativecode;public class Value {private String input,answer;public Value(String input){this.input=input;}public String getInput(){return input;}public void setAnswer(String a){answer=a;}public String getAnswer(){return answer;}}'''
    suite.scenarios[0].native_entry.arguments=[]
    from models.native_boundary_value import NativeBoundaryValue
    suite.scenarios[0].native_entry.arguments=[NativeBoundaryValue(type_name='nativecode.Value',source='object',arguments=[dict(type_name='java.lang.String',source='fixture',key='input')])]
    from models.native_boundary_projection import NativeBoundaryProjection
    suite.scenarios[0].native_entry.context_writes=[NativeBoundaryProjection(context_key='Answer',source='argument',argument_index=0,getters=['getAnswer'])]
    plan=comparison_plan('step',step,[NativeSourceFile(path='src/main/java/nativecode/Step.java',content=native),NativeSourceFile(path='src/main/java/nativecode/Value.java',content=dto),
        NativeSourceFile(path='src/main/java/nativecode/Client.java',content=client.replace('package example;','package nativecode;'))],bank,suite,'step-manifest')
    plan.original_framework.external_bindings={'example.Client.call(java.lang.String)':'service:call'}
    plan.native_external_bindings={'nativecode.Client.call(java.lang.String)':'service:call'}
    report=run_step_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'step',tool=boundary_tool)
    assert report['status']=='completed' and report['counts']['matched']==1,report
    assert report['cases'][0]['legacy']['output']==1 and report['cases'][0]['native']['context']['Answer']=='response'


def test_paired_jdbc_uses_same_rows_with_typed_collection(boundary_tool,tmp_path):
    original='''package example;import com.ibm.dse.base.*;import java.util.*;
public class Format {public void initializeFrom(Tag t){} public String format(Context c)throws Exception {
Map<?,?> row=(Map<?,?>)((List<?>)c.getValueAt("Rows")).get(0);
try(var p=c.getConnection().prepareStatement("SELECT V FROM T WHERE K = ?")){p.setString(1,(String)row.get("name"));try(var r=p.executeQuery()){return "<v>"+(r.next()?r.getString(1):"")+"</v>";}}}}'''
    native='''package nativecode;import java.sql.*;import java.util.*;
public class Format {public String format(Connection c,List<Row> rows)throws Exception {
try(var p=c.prepareStatement("SELECT V FROM T WHERE K = ?")){p.setString(1,rows.get(0).getName());try(var r=p.executeQuery()){return "<v>"+(r.next()?r.getString(1):"")+"</v>";}}}}'''
    row='package nativecode;public class Row {private String name;public Row(String n){name=n;}public String getName(){return name;}}'
    bank=SharedFixtureBank(fixtures={'rows':dict(value=[{'name':'k'}]),'db':dict(kind='database',value={'queries':[dict(sql='SELECT V FROM T WHERE K = ?',parameters=['k'],columns=['V'],rows=[['found']])]})})
    binding=dict(owner_type='nativecode.Format',method_name='format',arguments=[dict(type_name='java.sql.Connection',source='resource',key='db'),
        dict(type_name='java.util.List',source='collection',key='rows',element=dict(type_name='nativecode.Row',source='object',arguments=[dict(type_name='java.lang.String',source='item',key='/name')]))])
    suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='whole_database_format',purpose='Whole format with real prepared-query fixture',direction='format',
        native_entry=binding,inputs={'rows':dict(fixture_id='rows')},composer_context={'Rows':dict(fixture_id='rows')},resources={'db':dict(fixture_id='db')},composer_resource_setters={'setConnection':'db'})])
    original_format=original_unit([*demo_sources(),source('format',original)],dict(java_class='example.Format',attributes={}))
    plan=comparison_plan('database-format',original_format,[NativeSourceFile(path='src/main/java/nativecode/Format.java',content=native),NativeSourceFile(path='src/main/java/nativecode/Row.java',content=row)],bank,suite,'db-manifest')
    report=run_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'db',tool=boundary_tool)
    assert report['counts']['matched']==1,report
    assert report['cases'][0]['legacy']['output']=='<v>found</v>'
    assert report['cases'][0]['legacy']['resource_events'][0]['arguments']==['k']


def test_real_junit_runs_shared_fixture_and_publishes_receipt(boundary_tool,tmp_path):
    from runtime.test_assets.junit_support import install_runtime,dependency,stage
    from runtime.test_assets.preparation import asset_scope
    from models.native_test_bundle import NativeTestBundle
    from models.maven_dependency import MavenDependency
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from runtime.managed_projects import create_build_context
    profile=PipelineConfiguration(java_version=25,test_preparation={'mode':'ai_shared_fixtures_v1'})
    install_runtime(profile)
    bank=SharedFixtureBank(fixtures={'flag':dict(value=True)})
    scenarios=JunitScenarioSuite(scenarios=[dict(scenario_id='small_boolean',purpose='Single native method',
        native_entry=dict(owner_type='nativecode.Format',method_name='format',arguments=[dict(type_name='java.lang.Boolean',source='fixture',key='flag')]),
        inputs={'flag':dict(fixture_id='flag')},assertions=['Returns true text'])])
    root,manifest=publish(tmp_path/'assets','junit',{},bank,scenarios,ComparisonScenarioSuite());h=digest(manifest.model_dump(mode='json'))
    test='''package nativecode;import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;
import il.co.dcd.verification.fixtures.FixtureStore;
public class FormatTest {@Test public void smallBoolean()throws Exception {var result=FixtureStore.open("src/test/resources/shared-test-assets/HASH","HASH").run("small_boolean");assertNull(result.exception());assertEquals("true",result.value());}}'''.replace('HASH',h)
    tests=NativeTestBundle(files=[dict(path='src/test/java/nativecode/FormatTest.java',content=test)],fixture_manifest_hash=h,scenario_methods={'small_boolean':'nativecode.FormatTest#smallBoolean'})
    assets=dict(root=str(root),manifest_hash=h,bank=bank,junit=scenarios,comparisons=ComparisonScenarioSuite(),tests=tests)
    project=tmp_path/'project'
    with asset_scope(assets):
        result,_=accept_bundle(project,{'src/main/java/nativecode/Format.java':'package nativecode;public class Format {public String format(Boolean value){return String.valueOf(value);}}',tests.files[0].path:test},
            create_build_context,profile,[dependency(),MavenDependency(group_id='org.junit.jupiter',artifact_id='junit-jupiter',version='5.10.0',scope='test')],required_tests=[tests.files[0].path])
    assert result['tests_passed'] and result['test_count']==1
    assert (project/'src/test/resources/shared-test-assets'/h/'fixtures.json').exists()


def test_unknown_library_calls_run_in_both_format_directions(boundary_tool,tmp_path):
    from models.format_comparison_plan import FormatComparisonPlan
    original='''package example;import com.ibm.dse.base.*;import java.util.concurrent.atomic.AtomicInteger;import java.util.function.IntSupplier;
public class Format {public void initializeFrom(Tag t){} private int count(){var n=new AtomicInteger();IntSupplier next=n::incrementAndGet;return next.getAsInt();}
public String format(Context c){return "<v>"+count()+"</v>";}public void unformat(String xml,Context c){c.setValueAt("value",count());}}'''
    native='''package nativecode;import java.util.concurrent.atomic.AtomicInteger;import java.util.function.IntSupplier;
public class Format {private int count(){var n=new AtomicInteger();IntSupplier next=n::incrementAndGet;return next.getAsInt();}
public String format(){return "<v>"+count()+"</v>";}public Integer unformat(String xml){return count();}}'''
    plan=FormatComparisonPlan(label='ordinary-library',scope='configured',
        original_unit=original_unit([*demo_sources(),source('format',original)],dict(java_class='example.Format',attributes={})),
        native_sources=[NativeSourceFile(path='src/main/java/nativecode/Format.java',content=native)],
        entries={'format':dict(direction='format',binding=dict(owner_type='nativecode.Format',method_name='format')),
                 'unformat':dict(direction='unformat',binding=dict(owner_type='nativecode.Format',method_name='unformat',arguments=[dict(type_name='java.lang.String',source='xml')],context_writes=[dict(context_key='value',source='result')]))},
        cases=[dict(case_id='format',binding_id='format'),dict(case_id='unformat',binding_id='unformat',input_xml='<v>1</v>')])
    report=run_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'library',tool=boundary_tool)
    assert report['counts']['matched']==2,report


def test_operation_step_keeps_unknown_call_guard(boundary_tool,tmp_path):
    original='''package example;import com.ibm.dse.base.Context;import java.util.concurrent.atomic.AtomicInteger;
public class Step {public void setContext(Context c){}public int execute(){return new AtomicInteger().incrementAndGet();}}'''
    native='''package nativecode;public class Step {public int execute(){return 1;}}'''
    step=unit('configured_step','example.Step',sources=[*demo_sources(),source('step',original)])
    bank=SharedFixtureBank(fixtures={'unused':dict(value=None)});suite=ComparisonScenarioSuite(scenarios=[dict(scenario_id='step',purpose='Retain operation policy',direction='step_execute',native_entry=dict(owner_type='nativecode.Step',method_name='execute'))])
    plan=comparison_plan('step-policy',step,[NativeSourceFile(path='src/main/java/nativecode/Step.java',content=native)],bank,suite,'policy-test')
    report=run_step_comparison(plan,PipelineConfiguration(java_version=25,format_comparison={'enabled':True,'collect_facts':False}),tmp_path/'step-policy',tool=boundary_tool)
    assert report['counts']['execution_failed']==1,report
    assert 'Uncontrolled external dependency' in str(report['cases'][0]['limitations'])
