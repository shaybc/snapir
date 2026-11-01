package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Remove only proven-dead calls or exact fresh-receiver alternatives from the conservative graph. */
final class StaticReachabilityExclusions {
    private StaticReachabilityExclusions() { }

    static Map<String, Object> inspect(Element input, SourceCatalog catalog) {
        var edges = BoundaryValues.children(input, "edge");
        Map<String, Set<String>> selected = new HashMap<>();
        Set<String> changed = new HashSet<>(), disabled = new HashSet<>(), active = new HashSet<>();
        if (BoundaryValues.children(input, "root").stream().noneMatch(root -> root.getAttribute("kind").equals("entry"))) return Map.of();
        for (Element root : BoundaryValues.children(input, "root")) active.add(root.getAttribute("id"));
        for (Element edge : edges) {
            Set<String> candidates = new HashSet<>();
            for (Element value : BoundaryValues.children(edge, "candidate")) candidates.add(value.getAttribute("id"));
            Node site = site(edge, catalog);
            CodeNode owner = catalog.nodes.get(edge.getAttribute("from_id"));
            if (site != null && owner != null && !StaticExclusionAnalysis.deadBranch(site,
                    ConfiguredGuardValues.evaluators(owner, catalog, input)).isEmpty()) {
                candidates.clear(); disabled.add(edge.getAttribute("id"));
            }
            else if (site instanceof MethodCallExpr call && call.getScope().orElse(null) instanceof ObjectCreationExpr receiver
                && receiver.getAnonymousClassBody().isEmpty()) {
                try {
                    var method = call.resolve().toAst(MethodDeclaration.class).orElseThrow();
                    var target = catalog.find(method);
                    if (target != null && candidates.contains(target.id) && !method.isAbstract()) candidates.retainAll(Set.of(target.id));
                } catch (RuntimeException unknown) { /* Retain every possible target. */ }
            }
            selected.put(edge.getAttribute("id"), candidates);
            if (candidates.size() != BoundaryValues.children(edge, "candidate").size()) changed.add(edge.getAttribute("id"));
        }
        boolean expanded;
        do {
            expanded = false;
            for (Element edge : edges) if (edge.getAttribute("from_id").isEmpty() || active.contains(edge.getAttribute("from_id")))
                expanded |= active.addAll(selected.get(edge.getAttribute("id")));
        } while (expanded);
        // An unresolved active call could reach a discarded candidate. Absence from samples proves nothing.
        if (edges.stream().anyMatch(edge -> Boolean.parseBoolean(edge.getAttribute("unbounded"))
            && (edge.getAttribute("from_id").isEmpty() || active.contains(edge.getAttribute("from_id")))
            && !disabled.contains(edge.getAttribute("id")))) return Map.of();
        Map<String, Object> result = new HashMap<>();
        for (Element item : BoundaryValues.children(input, "item")) {
            String id = item.getAttribute("code_node_id");
            if (active.contains(id) || changed.isEmpty()) continue;
            CodeNode node = catalog.nodes.get(id);
            if (node == null) continue;
            boolean uncertain = edges.stream().anyMatch(edge -> Boolean.parseBoolean(edge.getAttribute("uncertain"))
                && BoundaryValues.children(edge, "candidate").stream().anyMatch(candidate -> candidate.getAttribute("id").equals(id)));
            boolean opposite = opposite(node, input.getAttribute("kind"));
            if (opposite || uncertain) result.put(item.getAttribute("id"), Map.of("reason", opposite ? "other_direction" : "uncertain_target_not_selected",
                "rule_id", "proven_inactive_call_path", "code_node_id", id, "pruned_edges", new TreeSet<>(changed)));
        }
        return result;
    }

    private static Node site(Element edge, SourceCatalog catalog) {
        CodeNode owner = catalog.nodes.get(edge.getAttribute("from_id"));
        if (owner == null || edge.getAttribute("start_line").isEmpty()) return null;
        return owner.anchor.findAll(Node.class).stream().filter(node -> node instanceof MethodCallExpr || node instanceof ObjectCreationExpr)
            .filter(node -> node.getRange().map(range -> range.begin.line == Integer.parseInt(edge.getAttribute("start_line"))
                && range.begin.column == Integer.parseInt(edge.getAttribute("start_column"))
                && range.end.line == Integer.parseInt(edge.getAttribute("end_line"))
                && range.end.column == Integer.parseInt(edge.getAttribute("end_column"))).orElse(false)).findFirst().orElse(null);
    }

    private static boolean opposite(CodeNode node, String kind) {
        if (!(node.anchor instanceof MethodDeclaration method)) return false;
        try {
            if (kind.equals("request_unformat") && method.getNameAsString().equals("format") && method.getParameters().size() == 1)
                return method.getType().resolve().describe().equals("java.lang.String")
                    && method.getParameter(0).getType().resolve().describe().equals("com.ibm.dse.base.Context");
            if (kind.equals("response_format") && method.getNameAsString().equals("unformat") && method.getParameters().size() == 2)
                return method.getType().isVoidType() && method.getParameter(0).getType().resolve().describe().equals("java.lang.String")
                    && method.getParameter(1).getType().resolve().describe().equals("com.ibm.dse.base.Context");
        } catch (RuntimeException unknown) { return false; }
        return false;
    }
}
