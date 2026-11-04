"""Static native configuration is explicit, fixture-backed and restored after each case."""
import os
from test_shared_fixture_execution import boundary_tool,jdk
from models.shared_test_fixture import SharedFixtureBank
from models.junit_test_scenario import JunitScenarioSuite
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.native_unit_bundle import NativeSourceFile
from runtime.test_assets.store import publish
from runtime.test_assets.validation import validate_suite
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from runtime.java_toolchain import run_java


def test_fixture_static_configuration_restores_actual_previous_values_on_success_and_failure(boundary_tool,tmp_path):
    options='''package nativecode;import java.util.*;public class Options {
private static Set<String> channels=Set.of(),exclusions=Set.of();
public static void configure(Set<String> c,Set<String> e){channels=Set.copyOf(c);exclusions=Set.copyOf(e);}
public static Set<String> channels(){return channels;}public static Set<String> exclusions(){return exclusions;}}'''
    code='''package nativecode;public class Sample {
public String read(){return Options.channels().iterator().next()+":"+Options.exclusions().iterator().next();}
public String failure(){throw new IllegalArgumentException("business failure");}}'''
    bank=SharedFixtureBank(fixtures={'channels':dict(value=['scenario-channel']),'exclusions':dict(value=['scenario-exclusion'])})
    def collection(key):return dict(type_name='java.util.Set',source='collection',key=key,element=dict(type_name='java.lang.String',source='item',key=''))
    setup=dict(owner_type='nativecode.Options',method_name='configure',arguments=[collection('channels'),collection('exclusions')],restore_getters=['channels','exclusions'])
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id=name,purpose='Isolated static setup',native_entry=dict(owner_type='nativecode.Sample',method_name=name),
        setup=[setup],inputs={key:dict(fixture_id=key) for key in bank.fixtures},assertions=['Runs with case settings and restores actual previous settings']) for name in ('read','failure')])
    sources=[NativeSourceFile(path='src/main/java/nativecode/Options.java',content=options),NativeSourceFile(path='src/main/java/nativecode/Sample.java',content=code)]
    validate_suite(suite,bank,128,native_sources=sources)
    root,manifest=publish(tmp_path/'assets','static-setup',{},bank,suite,ComparisonScenarioSuite())
    driver='''import java.util.*;import il.co.dcd.verification.fixtures.*;
public class Driver {public static void main(String[] args)throws Exception {
nativecode.Options.configure(Set.of("previous-channel"),Set.of("previous-exclusion"));
var store=FixtureStore.open(args[0],args[1]);
for(int i=0;i<2;i++){
if(!"scenario-channel:scenario-exclusion".equals(store.run("read").value()))throw new AssertionError("setup missing");
if(!(store.run("failure").exception() instanceof IllegalArgumentException))throw new AssertionError("business exception lost");
if(!nativecode.Options.channels().equals(Set.of("previous-channel"))||!nativecode.Options.exclusions().equals(Set.of("previous-exclusion")))throw new AssertionError("static settings leaked");
}
}}'''
    paths=[]
    for name,text in [('Options.java',options),('Sample.java',code),('Driver.java',driver)]:
        path=tmp_path/name;path.write_text(text);paths.append(str(path))
    classes=tmp_path/'classes';classes.mkdir()
    compiled=run_java(['javac','-cp',str(boundary_tool),'-d',str(classes),*paths],capture_output=True,text=True,timeout=60,check=False)
    assert compiled.returncode==0,compiled.stderr
    execution=run_java(['java','-ea','-cp',os.pathsep.join([str(classes),str(boundary_tool)]),'Driver',str(root),digest(manifest.model_dump(mode='json'))],cwd=tmp_path,capture_output=True,text=True,timeout=60,check=False)
    assert execution.returncode==0,execution.stderr
