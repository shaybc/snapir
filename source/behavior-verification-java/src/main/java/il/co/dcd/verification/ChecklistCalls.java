package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import java.util.*;

/** Preserve resolved, implicit and unresolved calls from the existing call graph. */
final class ChecklistCalls {
    private final ParserChecklist checklist;
    ChecklistCalls(ParserChecklist checklist) { this.checklist = checklist; }

    void analyze() {
        for (CallEdge edge : checklist.graph.edges) {
            if (!invocation(edge.kind) || edge.from.isEmpty()) continue;
            CodeNode owner = checklist.graph.nodes.get(edge.from);
            if (owner == null) continue;
            Node site = edge.site == null ? owner.anchor : edge.site;
            var item = checklist.add(owner, site, "call", edge.kind + ":" + edge.declaredTarget)
                .property("target", edge.declaredTarget).property("binding_kind", edge.kind)
                .property("binding_status", edge.unbounded ? "unbounded" : edge.uncertain ? "uncertain" : "resolved")
                .property("boundary_classification", "pending");
            boolean external = edge.candidates.stream().anyMatch(value -> value.startsWith("external:"));
            boolean supplied = edge.candidates.stream().anyMatch(value -> !value.startsWith("external:"));
            item.property("target_scope", external ? supplied ? "supplied_and_external" : "external" : supplied ? "supplied" : "unresolved");
            item.candidates.addAll(edge.candidates);
            List<Expression> arguments = arguments(site);
            if (item.arguments.isEmpty()) for (Expression argument : arguments) item.arguments.add(argument.toString());
            // Every opaque/internal call may mutate collaborators. Do not invent a tag-specific write catalog.
            var effect = checklist.add(owner, site, "write", "potential_call_effect:" + edge.kind + ":" + edge.declaredTarget)
                .property("target", edge.declaredTarget).property("observability", "not_classified")
                .property("certainty", "potential_effect_only");
            effect.candidates.addAll(edge.candidates);
            if (effect.arguments.isEmpty()) effect.arguments.addAll(item.arguments);
            checklist.add(owner, site, "exception", "potential_call_exception:" + edge.kind + ":" + edge.declaredTarget)
                .property("target", edge.declaredTarget).property("exception_type", "not_inferred");
        }
    }

    private static boolean invocation(String kind) {
        return kind.contains("call") || kind.contains("constructor") || kind.contains("dispatch")
            || kind.contains("reference") || kind.startsWith("implicit_") || kind.equals("unresolved_construction");
    }

    private static List<Expression> arguments(Node site) {
        if (site instanceof MethodCallExpr value) return value.getArguments();
        if (site instanceof ObjectCreationExpr value) return value.getArguments();
        if (site instanceof ExplicitConstructorInvocationStmt value) return value.getArguments();
        return List.of();
    }
}
