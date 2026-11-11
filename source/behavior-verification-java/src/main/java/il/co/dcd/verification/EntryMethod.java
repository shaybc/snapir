package il.co.dcd.verification;

import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import java.util.ArrayList;
import java.util.List;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** Resolve the exact instance-method contract, including inherited implementations. */
final class EntryMethod {
    private EntryMethod() { }

    static void write(Element entry, SourceScope sources, XMLStreamWriter output) throws XMLStreamException {
        String implementation = entry.getAttribute("implementation");
        var resolved = resolve(entry, sources);
        MethodDeclaration method = resolved.toAst(MethodDeclaration.class)
            .orElseThrow(() -> new IllegalStateException("Entry method has no supplied Java source: declaring_class="
                + resolved.declaringType().getQualifiedName() + "; signature=" + resolved.getQualifiedSignature()));
        if (method.getBody().isEmpty()) throw new IllegalStateException("Entry method has no executable body");
        if (FormatLifecycle.format(entry)) FormatLifecycle.sequence(entry, sources, resolved);
        var unit = method.findCompilationUnit().orElseThrow();
        Element source = sources.evidence(unit);
        var range = method.getRange().orElseThrow();
        output.writeStartElement("method");
        output.writeAttribute("implementation_class", implementation);
        output.writeAttribute("declaring_class", resolved.declaringType().getQualifiedName());
        output.writeAttribute("signature", resolved.getQualifiedSignature());
        output.writeAttribute("return_type", resolved.getReturnType().describe());
        output.writeAttribute("source_identity", source.getAttribute("identity"));
        output.writeAttribute("source_hash", source.getAttribute("hash"));
        output.writeAttribute("start_line", Integer.toString(range.begin.line));
        output.writeAttribute("end_line", Integer.toString(range.end.line));
        output.writeStartElement("excerpt");
        output.writeCharacters(method.getTokenRange().orElseThrow().toString());
        output.writeEndElement();
        output.writeEndElement();
        if (FormatLifecycle.format(entry)) FormatLifecycle.write(entry, sources, resolved, output);
    }

    static ResolvedMethodDeclaration resolve(Element entry, SourceScope sources) {
        String implementation = entry.getAttribute("implementation");
        var declaration = sources.solverFor(implementation).solveType(implementation);
        List<ResolvedMethodDeclaration> matches = new ArrayList<>();
        // Prefer the actual override before examining inherited methods.
        if (FormatLifecycle.format(entry)) {
            for (var method : FormatLifecycle.methods(entry,sources)) if (matches(entry,method)) matches.add(method);
        } else for (var method : declaration.getDeclaredMethods()) {
            if (matches(entry, method)) matches.add(method);
        }
        if (matches.isEmpty() && !FormatLifecycle.format(entry)) {
            for (var usage : declaration.getAllMethods()) {
                if (matches(entry, usage.getDeclaration())) matches.add(usage.getDeclaration());
            }
        }
        if (matches.isEmpty()) {
            var alternative = FormatLifecycle.fallback(entry, sources);
            if (alternative != null) matches.add(alternative);
        }
        if (matches.size() != 1) throw new IllegalStateException("Entry method must resolve uniquely: " + implementation + "." + entry.getAttribute("method") + " (matches=" + matches.size() + ")");
        return matches.get(0);
    }

    private static boolean matches(Element entry, ResolvedMethodDeclaration method) {
        if (!method.getName().equals(entry.getAttribute("method")) || method.isStatic()
                || method.accessSpecifier() != com.github.javaparser.ast.AccessSpecifier.PUBLIC) return false;
        var parameters = entry.getElementsByTagName("parameter");
        if (method.getNumberOfParams() != parameters.getLength()) return false;
        if (!method.getReturnType().describe().equals(entry.getAttribute("returns"))) return false;
        for (int index = 0; index < parameters.getLength(); index++) {
            String expected = ((Element) parameters.item(index)).getAttribute("type");
            String actual = method.getParam(index).getType().describe();
            if (expected.equals("Context")) {
                if (!actual.startsWith("com.ibm.") || !actual.endsWith(".Context")) return false;
            } else if (!expected.equals(actual)) return false;
        }
        return true;
    }
}
