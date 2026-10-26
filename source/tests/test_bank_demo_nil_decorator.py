"""Execute the demo decorator source as an oracle for runtime-dependent attributes."""

from pathlib import Path
import subprocess


def test_demo_nil_policy_uses_runtime_context_and_configuration(tmp_path):
    root = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    harness = tmp_path / 'NilPolicyCheck.java'
    harness.write_text('''import java.util.Set;
import com.ibm.dse.base.Context;
import com.ibm.dse.base.SchemaValidationSettings;
import com.ibm.il.dse.cc.decorator.NilDecorator;
public class NilPolicyCheck {
    static void check(boolean condition) {
        if (!condition) throw new AssertionError("Unexpected nil policy");
    }
    public static void main(String[] args) {
        NilDecorator decorator = new NilDecorator();
        Context context = new Context();
        context.setValueAt("CHANNEL_NAME", "SME");
        context.setValueAt("APPLICATION", "BANK");
        check(decorator.formatXmlAttributes(context, null).isEmpty());
        SchemaValidationSettings.configure(Set.of("sme"), Set.of("excluded"));
        check("true".equals(decorator.formatXmlAttributes(context, null).get("xsi:nil")));
        check("true".equals(decorator.formatXmlAttributes(context, "").get("xsi:nil")));
        check(decorator.formatXmlAttributes(context, " ").isEmpty());
        check(decorator.formatXmlAttributes(context, "message").isEmpty());
        context.setValueAt("APPLICATION", "EXCLUDED");
        check(decorator.formatXmlAttributes(context, null).isEmpty());
        context.setValueAt("APPLICATION", "BANK");
        context.setValueAt("CHANNEL_NAME", "IVR");
        check(decorator.formatXmlAttributes(context, null).isEmpty());
        context.setValueAt("CHANNEL_NAME", "SME");
        SchemaValidationSettings.configure(Set.of(), Set.of());
        check(decorator.formatXmlAttributes(context, null).isEmpty());
        SchemaValidationSettings.configure(Set.of("sme"), Set.of());
        context.setValueAt("APPLICATION", null);
        check(decorator.formatXmlAttributes(context, null).isEmpty());
        context.setValueAt("CHANNEL_NAME", 42);
        check(decorator.formatXmlAttributes(context, null).isEmpty());
    }
}''')
    files = [root / ('com/ibm/dse/base/' + name + '.java') for name in
             ('Context', 'AttributeXmlFormatDecoratorImpl', 'SchemaValidationSettings')]
    files.append(root / 'com/ibm/il/dse/cc/decorator/NilDecorator.java')
    compile_result = subprocess.run(['javac', '-d', str(tmp_path), *map(str, files), str(harness)],
                                    capture_output=True, text=True, timeout=60)
    assert compile_result.returncode == 0, compile_result.stderr
    result = subprocess.run(['java', '-cp', str(tmp_path), 'NilPolicyCheck'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'NilDecorator error' in result.stderr
