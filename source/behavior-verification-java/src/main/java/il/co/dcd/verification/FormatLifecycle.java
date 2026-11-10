package il.co.dcd.verification;

import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import java.util.*;
import org.w3c.dom.Element;
import javax.xml.stream.XMLStreamWriter;
import javax.xml.stream.XMLStreamException;

/** Resolve source-backed format boundaries; legacy ownership never dictates native architecture. */
final class FormatLifecycle {
    private FormatLifecycle() { }
    static boolean format(Element entry) { return !entry.getAttribute("kind").equals("configured_step"); }
    private static final Set<String> NAMES = Set.of("format","unformat","formatField","unformatField","beforeFormatDo","beforeUnformatDo");
    private static void add(Map<String, ResolvedMethodDeclaration> result, ResolvedMethodDeclaration method) {
        if (!NAMES.contains(method.getName())) return;
        var previous = result.get(method.getSignature());
        if (previous == null) { result.put(method.getSignature(),method); return; }
        if (previous.getQualifiedSignature().equals(method.getQualifiedSignature())) return;
        if (previous.isAbstract() != method.isAbstract()) {
            if (!method.isAbstract()) result.put(method.getSignature(),method);
            return;
        }
        String oldOwner = previous.declaringType().getQualifiedName(), owner = method.declaringType().getQualifiedName();
        if (method.declaringType().getAllAncestors().stream().anyMatch(parent -> parent.getQualifiedName().equals(oldOwner))) {
            result.put(method.getSignature(),method); return;
        }
        if (previous.declaringType().getAllAncestors().stream().noneMatch(parent -> parent.getQualifiedName().equals(owner)))
            throw new IllegalStateException("Ambiguous inherited format lifecycle declaration: " + method.getSignature());
    }
    static List<ResolvedMethodDeclaration> methods(Element entry, SourceScope sources) {
        var type = sources.solverFor(entry.getAttribute("implementation")).solveType(entry.getAttribute("implementation"));
        Map<String, ResolvedMethodDeclaration> result = new LinkedHashMap<>();
        for (var method : type.getDeclaredMethods()) add(result,method);
        for (var usage : type.getAllMethods()) add(result,usage.getDeclaration());
        return new ArrayList<>(result.values());
    }
    static String simple(String type) { return type.substring(type.lastIndexOf('.') + 1); }
    private static boolean parameters(ResolvedMethodDeclaration method, String... expected) {
        if (method.isStatic() || method.accessSpecifier() == com.github.javaparser.ast.AccessSpecifier.PRIVATE || method.getNumberOfParams() != expected.length) return false;
        for (int i = 0; i < expected.length; i++) {
            String actual = method.getParam(i).getType().describe();
            if (!simple(actual).equals(expected[i]) || expected[i].equals("String") && !actual.equals("java.lang.String")) return false;
        }
        return true;
    }
    private static ResolvedMethodDeclaration one(List<ResolvedMethodDeclaration> methods, String name, String... parameters) {
        var found = methods.stream().filter(method -> method.getName().equals(name) && parameters(method, parameters)).toList();
        if (found.size() > 1) throw new IllegalStateException("Ambiguous format lifecycle method: " + name);
        return found.isEmpty() ? null : found.get(0);
    }
    static ResolvedMethodDeclaration fallback(Element entry, SourceScope sources) {
        if (!format(entry)) return null;
        var methods = methods(entry, sources);
        boolean reading = entry.getAttribute("kind").equals("request_unformat");
        if (!entry.getAttribute("format_scope").equals("basic")) {
            // Operation is a distinct input, not a Context alias. The harness requires an explicit recipe.
            return reading ? one(methods, "unformat", "String", "Operation") : one(methods, "format", "KeyedCollection");
        }
        ResolvedMethodDeclaration selected = reading ? one(methods, "unformat", "String", "DataField")
            : one(methods, "formatField", "DataField");
        if (selected == null && reading) selected = one(methods, "unformatField", "String", "DataField");
        if (selected == null) return null;
        String hookName = reading ? "beforeUnformatDo" : "beforeFormatDo";
        var hook = reading ? one(methods, hookName, "DataElement", "FormatElement", "Context")
                           : one(methods, hookName, "DataElement", "Context");
        if (hook != null && calls(hook, selected.getName()) && !hook.getReturnType().isVoid() && valueCaller(sources, hook)) return hook;
        return selected;
    }
    private static boolean calls(ResolvedMethodDeclaration method, String name) {
        return method.toAst(MethodDeclaration.class).map(ast -> ast.findAll(MethodCallExpr.class).stream()
            .anyMatch(call -> call.getNameAsString().equals(name))).orElse(false);
    }
    static List<ResolvedMethodDeclaration> sequence(Element entry, SourceScope sources, ResolvedMethodDeclaration selected) {
        List<ResolvedMethodDeclaration> result = new ArrayList<>();
        if (entry.getAttribute("format_scope").equals("basic") && Set.of("formatField", "unformatField", "unformat").contains(selected.getName())
                && selected.getNumberOfParams() > 0 && simple(selected.getParam(selected.getNumberOfParams()-1).getType().describe()).equals("DataField")) {
            boolean reading = entry.getAttribute("kind").equals("request_unformat");
            var hook = reading ? one(methods(entry,sources), "beforeUnformatDo", "DataElement", "FormatElement", "Context")
                               : one(methods(entry,sources), "beforeFormatDo", "DataElement", "Context");
            if (hook != null) {
                // Do not invent hook order. Require an original orchestration body with resolved ordered calls.
                if (orderedCaller(sources, hook, selected) == null)
                    throw new IllegalStateException("Format lifecycle hook order has no supplied resolved caller: " + hook.getQualifiedSignature());
                result.add(hook);
            }
        }
        result.add(selected);
        for (var method : result) {
            var ast = method.toAst(MethodDeclaration.class).orElseThrow(() -> new IllegalStateException("Format lifecycle method has no supplied Java source: " + method.getQualifiedSignature()));
            sources.evidence(ast.findCompilationUnit().orElseThrow());
            if (ast.getBody().isEmpty()) throw new IllegalStateException("Format lifecycle method has no executable body: " + method.getQualifiedSignature());
        }
        return result;
    }
    private static boolean valueCaller(SourceScope sources, ResolvedMethodDeclaration hook) {
        for (String name : sources.typeNames) {
            var type = sources.solverFor(name).solveType(name).toAst(com.github.javaparser.ast.body.ClassOrInterfaceDeclaration.class);
            if (type.isEmpty()) continue;
            sources.bind(type.get());
            for (var call : type.get().findAll(MethodCallExpr.class)) {
                if (!same(call, hook)) continue;
                var parent = call.getParentNode();
                if (parent.isPresent() && parent.get() instanceof com.github.javaparser.ast.stmt.ReturnStmt returned
                        && returned.getExpression().map(call::equals).orElse(false)) return true;
            }
        }
        return false;
    }
    private static boolean direct(MethodCallExpr call) {
        var parent = call.getParentNode();
        return parent.isPresent() && (parent.get() instanceof com.github.javaparser.ast.stmt.ExpressionStmt statement
            && statement.getExpression().equals(call) || parent.get() instanceof com.github.javaparser.ast.stmt.ReturnStmt returned
            && returned.getExpression().map(call::equals).orElse(false));
    }
    private static MethodDeclaration orderedCaller(SourceScope sources, ResolvedMethodDeclaration hook, ResolvedMethodDeclaration selected) {
        for (String name : sources.typeNames) {
            var type = sources.solverFor(name).solveType(name).toAst(com.github.javaparser.ast.body.ClassOrInterfaceDeclaration.class);
            if (type.isEmpty()) continue;
            sources.bind(type.get());
            for (var body : type.get().getMethods()) {
                var calls = body.findAll(MethodCallExpr.class).stream().sorted(Comparator.comparing(call -> call.getBegin().orElseThrow())).toList();
                for (int i=0; i<calls.size(); i++) {
                    if (!direct(calls.get(i)) || !same(calls.get(i), hook)) continue;
                    for (int j=i+1; j<calls.size(); j++) {
                        // The same receiver expression is required; unrelated calls cannot establish a lifecycle.
                        if (direct(calls.get(j)) && calls.get(i).getScope().equals(calls.get(j).getScope())
                                && calls.get(i).findAncestor(com.github.javaparser.ast.stmt.BlockStmt.class).equals(calls.get(j).findAncestor(com.github.javaparser.ast.stmt.BlockStmt.class))
                                && !calls.get(i).getArguments().isEmpty() && !calls.get(j).getArguments().isEmpty()
                                && calls.get(i).getArgument(0).equals(calls.get(j).getArgument(calls.get(j).getArguments().size()-1))
                                && same(calls.get(j),selected)) return body;
                    }
                }
            }
        }
        return null;
    }
    private static boolean same(MethodCallExpr call, ResolvedMethodDeclaration target) {
        if (!call.getNameAsString().equals(target.getName()) || call.getArguments().size() != target.getNumberOfParams()) return false;
        try {
            var resolved = call.resolve();
            if (resolved.getQualifiedSignature().equals(target.getQualifiedSignature())) return true;
            if (!resolved.getSignature().equals(target.getSignature()) || !resolved.getReturnType().describe().equals(target.getReturnType().describe())) return false;
            return target.declaringType().getAllAncestors().stream().anyMatch(ancestor -> ancestor.getQualifiedName().equals(resolved.declaringType().getQualifiedName()));
        }
        catch (RuntimeException unresolved) { return false; }
    }
    static void write(Element entry, SourceScope sources, ResolvedMethodDeclaration selected, XMLStreamWriter output) throws XMLStreamException {
        var sequence = sequence(entry,sources,selected);
        output.writeStartElement("lifecycle");
        output.writeAttribute("version","format-lifecycle-v1");
        output.writeAttribute("direction",entry.getAttribute("kind").equals("request_unformat")?"unformat":"format");
        if (sequence.size() > 1) {
            var caller = orderedCaller(sources, sequence.get(0), selected);
            var proof = sources.evidence(caller.findCompilationUnit().orElseThrow());
            output.writeEmptyElement("ordering");
            output.writeAttribute("source_identity",proof.getAttribute("identity"));
            output.writeAttribute("source_hash",proof.getAttribute("hash"));
            output.writeAttribute("start_line",Integer.toString(caller.getBegin().orElseThrow().line));
            output.writeAttribute("end_line",Integer.toString(caller.getEnd().orElseThrow().line));
        }
        for (var method : sequence) {
            output.writeStartElement("invocation");
            output.writeAttribute("method",method.getName());
            output.writeAttribute("declaring_class",method.declaringType().getQualifiedName());
            output.writeAttribute("signature",method.getQualifiedSignature());
            output.writeAttribute("returns",method.getReturnType().describe());
            var ast = method.toAst(MethodDeclaration.class).orElseThrow();
            var evidence = sources.evidence(ast.findCompilationUnit().orElseThrow());
            output.writeAttribute("source_identity",evidence.getAttribute("identity"));
            output.writeAttribute("source_hash",evidence.getAttribute("hash"));
            for (int i=0;i<method.getNumberOfParams();i++) {
                output.writeEmptyElement("parameter"); output.writeAttribute("type",method.getParam(i).getType().describe());
            }
            output.writeEndElement();
        }
        output.writeEndElement();
    }
}
