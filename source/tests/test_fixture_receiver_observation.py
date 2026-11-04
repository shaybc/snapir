"""Expose the real invoked receiver without replacing assertions or re-executing business code."""
import os
from test_shared_fixture_execution import boundary_tool,jdk
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from runtime.test_assets.store import publish
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from runtime.java_toolchain import run_java


def test_fixture_result_retains_actual_receiver_and_partial_state(boundary_tool,tmp_path):
    code='''package nativecode;public class Sample {
private String state="initial";public Sample(){}public Sample(String value){state=value;}
public int execute(String value){state=value;return 7;}
public String failure(String value){state=value;throw new IllegalArgumentException("business failure");}
public String getState(){return state;}public static String echo(String value){return value;}}'''
    bank=SharedFixtureBank(fixtures={'input':dict(value='actual-value')})
    argument=dict(type_name='java.lang.String',source='fixture',key='input')
    scenarios=[dict(scenario_id=name,purpose='Actual receiver observations',native_entry=dict(owner_type='nativecode.Sample',method_name=name,arguments=[argument],static_method=name=='echo'),
        inputs={'input':dict(fixture_id='input')},assertions=['Receiver state is from the actual execution']) for name in ('execute','failure','echo')]
    scenarios.append(dict(scenario_id='constructor',purpose='Constructed receiver',entry_kind='constructor',native_entry=dict(owner_type='nativecode.Sample',method_name='<init>',constructor_arguments=[argument]),inputs={'input':dict(fixture_id='input')},assertions=['The value and receiver are the same constructed object']))
    root,manifest=publish(tmp_path/'assets','receiver',{},bank,JunitScenarioSuite(scenarios=scenarios),ComparisonScenarioSuite())
    driver='''import il.co.dcd.verification.fixtures.*;
public class Driver {public static void main(String[] args)throws Exception {
var store=FixtureStore.open(args[0],args[1]);var result=store.run("execute");
if(!Integer.valueOf(7).equals(result.value())||!"actual-value".equals(((nativecode.Sample)result.receiver()).getState()))throw new AssertionError("receiver state missing");
var failed=store.run("failure");if(!(failed.exception() instanceof IllegalArgumentException)||!"actual-value".equals(((nativecode.Sample)failed.receiver()).getState()))throw new AssertionError("partial state lost");
if(store.run("echo").receiver()!=null)throw new AssertionError("static receiver fabricated");
var constructed=store.run("constructor");if(constructed.receiver()!=constructed.value()||!"actual-value".equals(((nativecode.Sample)constructed.receiver()).getState()))throw new AssertionError("constructor receiver");
}}'''
    paths=[]
    for name,text in [('Sample.java',code),('Driver.java',driver)]:
        p=tmp_path/name;p.write_text(text);paths.append(str(p))
    classes=tmp_path/'classes';classes.mkdir()
    compiled=run_java(['javac','-cp',str(boundary_tool),'-d',str(classes),*paths],capture_output=True,text=True,timeout=60,check=False)
    assert compiled.returncode==0,compiled.stderr
    executed=run_java(['java','-ea','-cp',os.pathsep.join([str(classes),str(boundary_tool)]),'Driver',str(root),digest(manifest.model_dump(mode='json'))],cwd=tmp_path,capture_output=True,text=True,timeout=60,check=False)
    assert executed.returncode==0,executed.stderr
