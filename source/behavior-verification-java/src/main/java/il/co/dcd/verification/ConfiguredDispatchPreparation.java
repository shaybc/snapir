package il.co.dcd.verification;

import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Close only private child lists registered by the trusted configured-tree harness. */
final class ConfiguredDispatchPreparation {
    private ConfiguredDispatchPreparation() { }

    static Map<String, Object> inspect(Element input, SourceCatalog catalog, Map<String, Object> unsupported) {
        Map<String, Object> result = new TreeMap<>();
        Set<String> reachable = new HashSet<>();
        for (Element item : BoundaryValues.children(input, "item")) reachable.add(item.getAttribute("code_node_id"));
        Set<String> children = new TreeSet<>();
        for (Element component : ConfigurationPreparation.components(input))
            for (Element child : BoundaryValues.children(component, "component")) children.add(child.getAttribute("implementation"));
        if (children.isEmpty()) return result;
        for (Element edge : BoundaryValues.children(input, "edge")) {
            if (!edge.getAttribute("unbounded").equals("true") || !edge.getAttribute("kind").equals("method_call")) continue;
            unsupported.put(edge.getAttribute("id"), "missing_source_call");
            CodeNode owner = catalog.nodes.get(edge.getAttribute("from_id"));
            if (owner == null) continue;
            var calls = owner.anchor.findAll(MethodCallExpr.class).stream().filter(c -> c.getRange().isPresent()
                && c.getBegin().get().line == Integer.parseInt(edge.getAttribute("start_line"))
                && c.getBegin().get().column == Integer.parseInt(edge.getAttribute("start_column"))).toList();
            if (calls.size() != 1) continue;
            var call = calls.get(0);
            unsupported.put(edge.getAttribute("id"), "not_private_child_list_iteration");
            var loop = call.findAncestor(ForEachStmt.class).orElse(null);
            if (loop == null || !loop.getIterable().isNameExpr() || call.getScope().isEmpty() || !call.getScope().get().isNameExpr()
                || !call.getScope().get().asNameExpr().getNameAsString().equals(loop.getVariable().getVariable(0).getNameAsString())) continue;
            String fieldName = loop.getIterable().asNameExpr().getNameAsString();
            var type = catalog.types.get(owner.owner);
            var field = type == null ? Optional.<FieldDeclaration>empty() : type.getFieldByName(fieldName);
            if (field.isEmpty() || !field.get().isPrivate() || !field.get().isFinal() || field.get().isStatic() || field.get().getVariables().size() != 1
                || field.get().getVariable(0).getInitializer().isEmpty()
                || !field.get().getVariable(0).getInitializer().get().toString().replaceAll("\\s+", "").equals("newArrayList<>()")) continue;
            try {
                if (!field.get().getVariable(0).getInitializer().get().asObjectCreationExpr().resolve().declaringType().getQualifiedName().equals("java.util.ArrayList")) continue;
            } catch (RuntimeException unresolved) { continue; }
            var registrations = type.getMethodsByName("addChild");
            unsupported.put(edge.getAttribute("id"), "unsupported_registration_body");
            if (registrations.size() != 1 || registrations.get(0).getParameters().size() != 1 || registrations.get(0).getBody().isEmpty()
                || !registrations.get(0).getBody().get().toString().replaceAll("\\s+", "").equals(
                    "{" + fieldName + ".add(" + registrations.get(0).getParameter(0).getNameAsString() + ");}")) continue;
            boolean closed = true;
            CodeNode registration = catalog.find(registrations.get(0));
            unsupported.put(edge.getAttribute("id"), "reachable_collection_mutation_or_escape");
            for (CodeNode node : catalog.nodes.values()) {
                if (!reachable.contains(node.id) || node.body == null) continue;
                if (node.body.findAll(MethodCallExpr.class).stream().anyMatch(c -> c.getNameAsString().equals("addChild"))) closed = false;
                if (registration != null && node.id.equals(registration.id)) continue;
                for (NameExpr name : node.body.findAll(NameExpr.class)) if (name.getNameAsString().equals(fieldName)
                    && !(name.getParentNode().orElse(null) instanceof ForEachStmt each && each.getIterable() == name)) closed = false;
                if (node.body.findAll(FieldAccessExpr.class).stream().anyMatch(f -> f.getNameAsString().equals(fieldName))) closed = false;
            }
            // A configured subclass overriding registration could install arbitrary children.
            for (Element configured : ConfigurationPreparation.components(input)) {
                var childType = catalog.types.get(configured.getAttribute("implementation"));
                if (childType == null) { closed = false; continue; }
                try {
                    if (childType.resolve().getAllAncestors().stream().anyMatch(a -> !a.getQualifiedName().equals("java.lang.Object") && !catalog.types.containsKey(a.getQualifiedName()))) closed = false;
                    var methods = catalog.named("addChild", 1).stream().filter(n -> catalog.possiblySubtype(configured.getAttribute("implementation"), n.owner)).toList();
                    var selected = methods.stream().filter(n -> methods.stream().noneMatch(other -> other != n && catalog.possiblySubtype(other.owner, n.owner))).toList();
                    // Decorators need not implement child registration at all.
                    if (configured.getTagName().equals("component") && (selected.size() != 1 || registration == null || !selected.get(0).id.equals(registration.id))) closed = false;
                } catch (RuntimeException unresolved) { closed = false; }
            }
            Set<String> candidates = new TreeSet<>();
            if (closed) unsupported.put(edge.getAttribute("id"), "configured_dispatch_target_not_unique");
            try {
                var declaration = call.resolve();
                for (String child : children) {
                    var matches = catalog.dispatch(declaration).stream().filter(n -> catalog.possiblySubtype(child, n.owner)).toList();
                    var mostSpecific = matches.stream().filter(n -> matches.stream().noneMatch(other -> other != n && catalog.possiblySubtype(other.owner, n.owner))).toList();
                    if (mostSpecific.size() != 1 || !mostSpecific.get(0).kind.equals("method")) { closed = false; break; }
                    candidates.add(mostSpecific.get(0).id);
                }
            } catch (RuntimeException unresolved) { closed = false; }
            Set<String> supplied = new HashSet<>();
            for (Element candidate : BoundaryValues.children(edge, "candidate")) supplied.add(candidate.getAttribute("id"));
            if (closed && !candidates.isEmpty() && supplied.containsAll(candidates)) {
                unsupported.remove(edge.getAttribute("id"));
                result.put(edge.getAttribute("id"), Map.of(
                "rule", "private_final_list_trusted_tree_registration", "candidates", new ArrayList<>(candidates),
                "configured_child_types", new ArrayList<>(children), "source_identity", owner.source.getAttribute("identity"),
                "source_hash", owner.source.getAttribute("hash"), "code_node_id", owner.id));
            }
        }
        return result;
    }
}
