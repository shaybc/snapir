package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.stmt.ReturnStmt;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ClassLoaderTypeSolver;
import java.nio.file.*;
import java.util.*;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.stream.XMLOutputFactory;
import org.w3c.dom.Element;

/** Instrument disposable snapshots only; originals and parser provenance remain untouched. */
public final class HarnessInstrumentation {
    private HarnessInstrumentation() { }

    public static void main(String[] args) throws Exception {
        var factory = DocumentBuilderFactory.newInstance(); factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element manifest = factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        Set<String> issues = new TreeSet<>(); Map<String, String> bindings = new TreeMap<>();
        var bindingNodes = manifest.getElementsByTagName("external_binding");
        for (int index = 0; index < bindingNodes.getLength(); index++) {
            Element binding = (Element) bindingNodes.item(index); bindings.put(binding.getAttribute("target"), binding.getAttribute("canonical"));
        }
        try (SourceScope scope = new SourceScope(manifest)) {
            scope.solver.add(new ClassLoaderTypeSolver(HarnessInstrumentation.class.getClassLoader()));
            JavaParser parser = new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
            for (var child = manifest.getFirstChild(); child != null; child = child.getNextSibling()) {
                if (!(child instanceof Element source) || !source.getTagName().equals("source")) continue;
                var unit = parser.parse(source.getTextContent()).getResult().orElseThrow(); scope.bind(unit);
                Map<String, Node> locations = new HashMap<>();
                for (Node node : unit.findAll(Node.class)) locations.put(key(node), node);
                var probes = elements(manifest, "probe");
                probes.sort(Comparator.comparingInt((Element item) -> depth(locations.get(key(item)))).reversed());
                for (Element item : probes) {
                    if (!item.getAttribute("source_identity").equals(source.getAttribute("identity"))) continue;
                    Node node = locations.get(key(item));
                    if (node == null) { issues.add("Probe source node unavailable: " + item.getAttribute("id")); continue; }
                    if (item.getAttribute("kind").equals("branch")) HarnessProbes.branch(node, item);
                    else HarnessProbes.method(node, item.getAttribute("id"));
                }
                if (manifest.getAttribute("typed_native").equals("true")) {
                    for (MethodDeclaration method : unit.findAll(MethodDeclaration.class)) {
                        if (!method.isPublic() || method.getBody().isEmpty()) continue;
                        try {
                            var resolved = method.resolve();
                            List<String> parameters = new ArrayList<>();
                            for (int index = 0; index < resolved.getNumberOfParams(); index++)
                                parameters.add(resolved.getParam(index).getType().erasure().describe());
                            HarnessProbes.method(method, "native:" + resolved.declaringType().getQualifiedName() + "."
                                + resolved.getName() + "(" + String.join(", ", parameters) + ")");
                        } catch (RuntimeException unresolved) { issues.add("Native public API could not be instrumented: " + method.getSignature()); }
                    }
                }
                new HarnessCalls(bindings, issues, node -> included(node, source, manifest, bindings),
                    manifest.getAttribute("fixture_resources").equals("true"),
                    manifest.getAttribute("allow_unknown_calls").equals("true")).scan(unit);
                if (Set.of("legacy","original").contains(manifest.getAttribute("side"))) contextHooks(unit, manifest);
                String pkg = unit.getPackageDeclaration().map(value -> value.getNameAsString()).orElse("");
                String type = unit.getTypes().stream().filter(value -> value.isPublic()).findFirst().orElse(unit.getType(0)).getNameAsString();
                Path file = Path.of(args[1]).resolve(pkg.replace('.', '/')).resolve(type + ".java");
                Files.createDirectories(file.getParent()); Files.writeString(file, unit.toString());
            }
        }
        try (var stream = Files.newOutputStream(Path.of(args[2]))) {
            var writer = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8"); writer.writeStartElement("instrumentation");
            for (String issue : issues) { writer.writeEmptyElement("issue"); writer.writeAttribute("message", issue); }
            writer.writeEndElement(); writer.close();
        }
    }

    private static void contextHooks(com.github.javaparser.ast.CompilationUnit unit, Element manifest) {
        for (MethodDeclaration method : unit.findAll(MethodDeclaration.class)) {
            String owner = method.findAncestor(com.github.javaparser.ast.body.ClassOrInterfaceDeclaration.class)
                .flatMap(value -> value.getFullyQualifiedName()).orElse("");
            if (!owner.equals(manifest.getAttribute("context_class")) || method.getBody().isEmpty()) continue;
            if (method.getNameAsString().equals(manifest.getAttribute("context_remover")) && method.getParameters().size() == 1) {
                String key = method.getParameter(0).getNameAsString();
                if (!method.getType().asString().equals("Object")) throw new IllegalArgumentException("Framework remover needs an Object-returning adapter");
                for (ReturnStmt statement : new ArrayList<>(method.getBody().orElseThrow().findAll(ReturnStmt.class))) {
                    var block = com.github.javaparser.StaticJavaParser.parseBlock("{ Object boundaryRemovedValue = null; }");
                    block.getStatement(0).asExpressionStmt().getExpression().asVariableDeclarationExpr().getVariable(0)
                        .setInitializer(statement.getExpression().orElseThrow().clone());
                    block.addStatement(HarnessProbes.call("removed", new NameExpr(key), new NameExpr("boundaryRemovedValue")));
                    block.addStatement(new ReturnStmt(new NameExpr("boundaryRemovedValue"))); statement.replace(block);
                }
                continue;
            }
            if (method.getParameters().size() != 2 || !method.getNameAsString().equals(manifest.getAttribute("context_writer"))) continue;
            if (!method.getType().isVoidType() || !method.getBody().orElseThrow().findAll(ReturnStmt.class).isEmpty())
                throw new IllegalArgumentException("Framework writer requires an explicit adapter for nontrivial returns");
            method.getBody().orElseThrow().addStatement(HarnessProbes.call("written", new NameExpr(method.getParameter(0).getNameAsString()), new NameExpr(method.getParameter(1).getNameAsString())));
        }
    }
    private static List<Element> elements(Element parent, String name) {
        List<Element> result = new ArrayList<>(); var nodes = parent.getElementsByTagName(name);
        for (int index = 0; index < nodes.getLength(); index++) result.add((Element) nodes.item(index)); return result;
    }
    private static String key(Node node) { return node.getRange().map(range -> node.getClass().getSimpleName() + ":" + range.begin.line + ":" + range.begin.column + ":" + range.end.line + ":" + range.end.column).orElse(""); }
    private static String key(Element item) { return item.getAttribute("syntax_type") + ":" + item.getAttribute("start_line") + ":" + item.getAttribute("start_column") + ":" + item.getAttribute("end_line") + ":" + item.getAttribute("end_column"); }
    private static int depth(Node node) { int value = 0; while (node != null) { value++; node = node.getParentNode().orElse(null); } return value; }
    private static boolean included(Node node, Element source, Element manifest, Map<String, String> bindings) {
        var method = node.findAncestor(MethodDeclaration.class);
        if (method.isPresent()) {
            try { if (bindings.containsKey(method.get().resolve().getQualifiedSignature())) return false; }
            catch (RuntimeException ignored) { /* The call itself remains subject to resolution and fail-closed diagnostics. */ }
        }
        if (!manifest.getAttribute("side").equals("legacy")) return true;
        String owner = node.findAncestor(com.github.javaparser.ast.body.ClassOrInterfaceDeclaration.class)
            .flatMap(value -> value.getFullyQualifiedName()).orElse("");
        if (owner.equals(manifest.getAttribute("context_class")) && method.isPresent()
                && Set.of(manifest.getAttribute("context_writer"), manifest.getAttribute("context_remover"),
                    manifest.getAttribute("context_reader"), manifest.getAttribute("context_snapshot")).contains(method.get().getNameAsString())) return true;
        for (Element setting : elements(manifest, "setting_method")) if (owner.equals(setting.getAttribute("implementation"))) return true;
        var range = node.getRange();
        if (range.isEmpty()) return false;
        for (Element target : elements(manifest, "reachable")) {
            if (!target.getAttribute("source_identity").equals(source.getAttribute("identity"))) continue;
            var begin = new com.github.javaparser.Position(Integer.parseInt(target.getAttribute("start_line")), Integer.parseInt(target.getAttribute("start_column")));
            var end = new com.github.javaparser.Position(Integer.parseInt(target.getAttribute("end_line")), Integer.parseInt(target.getAttribute("end_column")));
            if (new com.github.javaparser.Range(begin, end).contains(range.orElseThrow())) return true;
        }
        return false;
    }
}
