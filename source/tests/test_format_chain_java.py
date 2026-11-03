"""Compile and execute native-only chain fixtures through the existing Maven/JUnit validator."""
from models.pipeline_configuration import PipelineConfiguration
from models.maven_dependency import MavenDependency
from runtime.java_toolchain import java_scope
from runtime.managed_projects import create_build_context
from runtime.behavior_conversion.bundle_output import accept_bundle
from test_format_chains import native_chain_case


def test_native_chain_order_reverse_removal_and_attribute_scope_with_real_junit(tmp_path):
    bundle,request=native_chain_case()
    files={file.path:file.content for file in bundle.files}
    prefix='src/main/java/nativecode/'
    files[prefix+'Basic.java']='''package nativecode;public class Basic {
 public String format(String input){return input==null?null:input.toUpperCase(java.util.Locale.ROOT);}
 public String unformat(String input){return input==null?null:input.toLowerCase(java.util.Locale.ROOT);}
}'''
    files[prefix+'First.java']='''package nativecode;public class First {
 public String add(String value){return value==null?null:"A"+value;}
 public String remove(String value){if(value==null)return null;if(!value.startsWith("A"))throw new IllegalArgumentException("prefix");return value.substring(1);}
}'''
    files[prefix+'Second.java']='''package nativecode;public class Second {
 public String add(String value){return value==null?null:new StringBuilder(value).reverse().toString();}
 public String remove(String value){return add(value);}
}'''
    files[prefix+'ReadChain.java']='''package nativecode;public class ReadChain {
 public String read(String input){String value=new Second().remove(input);value=new First().remove(value);return new Basic().unformat(value);}
}'''
    files[prefix+'Attributes.java']='''package nativecode;public record Attributes(boolean nil) {}'''
    files[prefix+'Nil.java']='''package nativecode;public class Nil {
 private final boolean enabled;public Nil(boolean enabled){this.enabled=enabled;}
 public Attributes attributes(String value){return new Attributes(enabled&&(value==null||value.isEmpty()));}
}'''
    files[prefix+'FieldMapper.java']='''package nativecode;public class FieldMapper {
 public String render(String input,boolean enabled){String value=new FormatChainExample().format(input);
  Attributes attributes=new Nil(enabled).attributes(value);
  return attributes.nil()?"<Value xsi:nil=\\\"true\\\"/>":value==null?"<Value/>":"<Value>"+value+"</Value>";
 }
}'''
    test='src/test/java/nativecode/ChainBehaviorTest.java'
    files[test]='''package nativecode;
import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;
public class ChainBehaviorTest {
 @Test public void forwardOrderPassesEachResult(){assertEquals("YXA",new Mapper().render("xy"));assertNull(new Mapper().render(null));}
 @Test public void reverseOrderBeforeBasicUnformat(){assertEquals("xy",new ReadChain().read("YXA"));assertThrows(IllegalArgumentException.class,()->new First().remove("YXA"));}
 @Test public void attributesObserveFinalFieldValueAndRuntimeSettings(){
  FieldMapper mapper=new FieldMapper();assertEquals("<Value xsi:nil=\\\"true\\\"/>",mapper.render(null,true));
  assertEquals("<Value/>",mapper.render(null,false));assertEquals("<Value>A</Value>",mapper.render("",true));
  assertEquals("<Value>YXA</Value>",mapper.render("xy",true));
 }
}'''
    profile=PipelineConfiguration(java_version=25)
    with java_scope(profile):
        validation,_=accept_bundle(tmp_path/'native-chains',files,create_build_context,profile,
            [MavenDependency(group_id='org.junit.jupiter',artifact_id='junit-jupiter',version='5.10.0',scope='test')],required_tests=[test])
    assert validation['build_passed'] and validation['tests_passed'] and validation['test_count']==3
