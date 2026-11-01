package il.co.dcd.verification;

import java.util.*;
import org.w3c.dom.Element;

/** Describe source-defined static Set configuration APIs; never execute or infer business policy. */
final class OriginalSettingsInspection {
    private OriginalSettingsInspection() { }
    static List<Map<String, Object>> inspect(Element input) throws Exception {
        List<Map<String, Object>> result = new ArrayList<>();
        try (SourceScope scope = new SourceScope(input)) {
            SourceCatalog catalog = new SourceCatalog(scope);
            Set<String> reachableOwners = new HashSet<>();
            for (Element item : il.co.dcd.verification.harness.BoundaryValues.children(input, "item")) {
                CodeNode node = catalog.nodes.get(item.getAttribute("code_node_id"));
                if (node != null) reachableOwners.add(node.owner);
            }
            for (var type : catalog.types.values()) for (var method : type.getMethods()) {
                if (!reachableOwners.contains(type.getFullyQualifiedName().orElse(""))) continue;
                if (!method.isPublic() || !method.isStatic() || !method.getType().isVoidType()
                    || method.getParameters().isEmpty() || method.getParameters().size() > 3) continue;
                try {
                    if (method.getParameters().stream().allMatch(parameter -> parameter.getType().resolve().erasure().describe().equals("java.util.Set"))) {
                        var source = scope.evidence(type.findCompilationUnit().orElseThrow());
                        result.add(Map.of("target", type.getFullyQualifiedName().orElseThrow() + "." + method.getNameAsString(),
                            "arity", method.getParameters().size(), "source_identity", source.getAttribute("identity"),
                            "source_hash", source.getAttribute("hash"), "source_content", source.getTextContent()));
                    }
                } catch (RuntimeException unresolved) { /* Unsupported controls remain absent, never guessed. */ }
            }
        }
        return result;
    }
}
