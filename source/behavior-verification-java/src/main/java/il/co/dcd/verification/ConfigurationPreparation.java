package il.co.dcd.verification;

import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Prepare source-backed configured coverage before any comparison input executes. */
final class ConfigurationPreparation {
    private ConfigurationPreparation() { }

    static Map<String, Object> inspect(Element input) throws Exception {
        try (SourceScope scope = new SourceScope(input)) {
            SourceCatalog catalog = new SourceCatalog(scope);
            if (!catalog.problems.isEmpty()) throw new IllegalArgumentException(catalog.problems.toString());
            Map<String, Object> unsupported = new TreeMap<>();
            var dispatches = ConfiguredDispatchPreparation.inspect(input, catalog, unsupported);
            return Map.of("version", "configured-coverage-preparation-v1",
                "branches", ConfiguredBranchPreparation.inspect(input, catalog),
                "dispatches", dispatches, "unsupported_dispatches", unsupported);
        }
    }

    static List<Element> components(Element input) {
        List<Element> result = new ArrayList<>();
        for (Element node : BoundaryValues.children(input, null)) {
            if (Set.of("component", "decorator").contains(node.getTagName())) result.add(node);
            if (!node.getTagName().equals("source")) result.addAll(components(node));
        }
        return result;
    }

    static boolean sameSite(com.github.javaparser.ast.Node node, Element item) {
        if (node.getRange().isEmpty()) return false;
        var r = node.getRange().orElseThrow();
        return node.getClass().getSimpleName().equals(item.getAttribute("syntax_type"))
            && r.begin.line == Integer.parseInt(item.getAttribute("start_line"))
            && r.begin.column == Integer.parseInt(item.getAttribute("start_column"))
            && r.end.line == Integer.parseInt(item.getAttribute("end_line"))
            && r.end.column == Integer.parseInt(item.getAttribute("end_column"));
    }
}
