package il.co.dcd.verification;

import com.github.javaparser.ast.expr.MethodCallExpr;
import java.util.Set;

/** Approved string-only XML codec boundary; file/URL/stream overloads remain uncontrolled. */
final class NativeCodecPolicy {
    private NativeCodecPolicy() { }
    static boolean method(String owner, String name, MethodCallExpr call) {
        if (!owner.equals("com.fasterxml.jackson.databind.ObjectMapper")
            && !owner.equals("com.fasterxml.jackson.dataformat.xml.XmlMapper")) return false;
        if (name.equals("writeValueAsString") && call.getArguments().size() == 1) return true;
        if (name.equals("readValue") && call.getArguments().size() == 2) {
            try { return call.getArgument(0).calculateResolvedType().describe().equals("java.lang.String")
                && call.getArgument(1).isClassExpr(); }
            catch (RuntimeException unresolved) { return false; }
        }
        if (name.equals("writeValue") && call.getArguments().size() == 2) {
            try { return Set.of("javax.xml.stream.XMLStreamWriter", "java.io.StringWriter")
                .contains(call.getArgument(0).calculateResolvedType().describe()); }
            catch (RuntimeException unresolved) { return false; }
        }
        return false;
    }
    static boolean constructor(String owner, int arguments) {
        return owner.equals("com.fasterxml.jackson.dataformat.xml.XmlMapper") && arguments == 0;
    }
}
