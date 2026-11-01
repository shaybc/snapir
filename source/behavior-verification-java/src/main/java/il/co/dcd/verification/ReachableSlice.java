package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import java.util.*;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** Traverse a conservative source graph; uncertainty never becomes a silent exclusion. */
final class ReachableSlice {
    final SourceCatalog catalog;
    final Map<String, CodeNode> nodes = new TreeMap<>();
    final List<CallEdge> edges = new ArrayList<>();
    final Set<String> issues = new TreeSet<>();
    final Set<String> externals = new TreeSet<>();
    final Map<String, Set<String>> roots = new TreeMap<>();
    final InitializationPaths initialization;
    private final Queue<CodeNode> pending = new ArrayDeque<>();

    ReachableSlice(SourceCatalog catalog) {
        this.catalog = catalog;
        initialization = new InitializationPaths(this);
    }

    void include(CodeNode node) {
        if (nodes.putIfAbsent(node.id, node) == null) pending.add(node);
    }

    void root(String kind, CodeNode node) {
        roots.computeIfAbsent(kind, ignored -> new TreeSet<>()).add(node.id);
        include(node);
    }

    void edge(String from, String kind, String target, List<CodeNode> candidates,
              boolean uncertain, boolean unbounded, String reason, Node site) {
        for (CodeNode node : candidates) include(node);
        edges.add(new CallEdge(from, kind, target, candidates.stream().map(node -> node.id).toList(), uncertain, unbounded, reason, site));
    }

    void external(String from, String kind, String signature, Node site, boolean uncertain, boolean unbounded, String reason) {
        String target = "external:" + signature;
        externals.add(target);
        edges.add(new CallEdge(from, kind, signature, List.of(target), uncertain, unbounded, reason, site));
    }

    void analyze(Element entry) {
        var declaration = EntryMethod.resolve(entry, catalog.scope);
        var ast = declaration.toAst(MethodDeclaration.class).orElseThrow();
        CodeNode entryNode = catalog.find(ast);
        if (entryNode == null) throw new IllegalStateException("Entry body was not indexed");
        root("entry", entryNode);
        var setup = entry.getElementsByTagName("setup");
        for (int index = 0; index < setup.getLength(); index++) {
            initialization.configured(((Element) setup.item(index)).getAttribute("implementation"));
        }
        var bindings = entry.getElementsByTagName("binding");
        for (int index = 0; index < bindings.getLength(); index++) {
            initialization.properties((Element) bindings.item(index), entry.getAttribute("kind").equals("configured_step"));
        }
        CallBindings calls = new CallBindings(this);
        while (!pending.isEmpty()) {
            CodeNode node = pending.remove();
            initialization.statics(node.owner, node.id);
            if (node.kind.equals("constructor") || node.kind.equals("implicit_constructor")) initialization.constructor(node);
            if (node.body != null) {
                catalog.scope.bind(node.body);
                calls.scan(node.body, node);
            }
        }
        issues.addAll(catalog.problems);
    }

    void write(XMLStreamWriter output) throws XMLStreamException {
        output.writeStartElement("reachability");
        output.writeAttribute("candidate_universe", "supplied_unit_evidence");
        output.writeAttribute("status", issues.isEmpty() && edges.stream().noneMatch(edge -> edge.unbounded) ? "analyzed" : "verification_incomplete");
        for (var root : roots.entrySet()) for (String id : root.getValue()) {
            output.writeEmptyElement("root"); output.writeAttribute("kind", root.getKey()); output.writeAttribute("id", id);
        }
        for (CodeNode node : nodes.values()) node.write(output);
        Set<String> seen = new HashSet<>();
        for (CallEdge edge : edges) {
            String key = edge.from + edge.kind + edge.declaredTarget + edge.candidates + (edge.site == null ? "" : edge.site.getRange());
            if (seen.add(key)) edge.write(catalog.scope, output);
        }
        for (String signature : externals) {
            output.writeEmptyElement("external"); output.writeAttribute("id", signature);
        }
        for (String issue : issues) {
            output.writeEmptyElement("issue"); output.writeAttribute("message", issue);
        }
        output.writeEndElement();
    }
}
