package il.co.dcd.verification;

import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Trust only a pinned, explicitly approved read-only Tag API during configured initialization. */
final class ConfiguredGuardValues {
    private ConfiguredGuardValues() { }

    static List<StaticConstantValues> evaluators(CodeNode owner, SourceCatalog catalog, Element input) {
        if (!(owner.anchor instanceof MethodDeclaration method) || !method.getNameAsString().equals("initializeFrom")
            || method.getParameters().size() != 1) return List.of();
        var incoming = BoundaryValues.children(input, "edge").stream().filter(edge ->
            BoundaryValues.children(edge, "candidate").stream().anyMatch(candidate -> candidate.getAttribute("id").equals(owner.id))).toList();
        if (incoming.isEmpty() || incoming.stream().anyMatch(edge -> !edge.getAttribute("kind").equals("configured_initialization")
            || !edge.getAttribute("from_id").isEmpty())) return List.of();
        String type;
        try { type = method.getParameter(0).getType().resolve().describe(); }
        catch (RuntimeException unresolved) { return List.of(); }
        var tagType = catalog.types.get(type);
        if (tagType == null) return List.of();
        String hash = catalog.scope.evidence(tagType.findCompilationUnit().orElseThrow()).getAttribute("hash");
        var contracts = BoundaryValues.children(input, "tag_contract").stream().filter(contract ->
            contract.getAttribute("class").equals(type) && contract.getAttribute("hash").equals(hash)).toList();
        if (contracts.size() != 1) return List.of();
        String parameter = method.getParameter(0).getNameAsString(), getter = contracts.get(0).getAttribute("getter");
        // No aliasing, passing the Tag to another method, mutation, or unapproved reads.
        for (NameExpr name : method.findAll(NameExpr.class)) {
            if (!name.getNameAsString().equals(parameter)) continue;
            if (!(name.getParentNode().orElse(null) instanceof MethodCallExpr call)
                || call.getScope().orElse(null) != name || !call.getNameAsString().equals(getter)
                || call.getArguments().size() != 1 || !(call.getArgument(0) instanceof StringLiteralExpr)) return List.of();
        }
        List<StaticConstantValues> result = new ArrayList<>();
        for (Element edge : incoming) {
            var bindings = BoundaryValues.children(input, "binding").stream().filter(binding ->
                binding.getAttribute("implementation").equals(edge.getAttribute("declared_target"))).toList();
            if (bindings.isEmpty()) return List.of();
            for (Element binding : bindings) {
                Map<String, String> attributes = new HashMap<>();
                for (Element attribute : BoundaryValues.children(binding, "attribute")) attributes.put(attribute.getAttribute("name"), attribute.getAttribute("value"));
                result.add(new StaticConstantValues(null, parameter, getter, attributes));
            }
        }
        return result;
    }
}
