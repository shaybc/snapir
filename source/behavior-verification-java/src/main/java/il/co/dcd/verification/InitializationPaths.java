package il.co.dcd.verification;

import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import java.util.*;

/** Retain configured setup, constructors, parent setup and field/static initialization. */
final class InitializationPaths {
    private final ReachableSlice graph;
    private final Set<String> staticVisited = new HashSet<>();
    private final Set<String> receiverVisited = new HashSet<>();

    InitializationPaths(ReachableSlice graph) { this.graph = graph; }

    void configured(String owner) {
        receiverVisited.add(owner);
        var type = graph.catalog.types.get(owner);
        if (type == null) {
            graph.issues.add("Configured setup class has no indexed source: " + owner);
            return;
        }
        List<CodeNode> constructors = graph.catalog.constructors(owner, -1);
        for (CodeNode node : constructors) graph.root("initialization", node);
        graph.edge("", "configured_construction", owner, constructors, constructors.size() != 1,
            constructors.isEmpty(), "All supplied constructor alternatives retained for configured setup", null);
        try {
            var declaration = graph.catalog.scope.solverFor(owner).solveType(owner);
            var methods = declaration.getAllMethods();
            List<CodeNode> setup = new ArrayList<>();
            boolean own = declaration.getDeclaredMethods().stream().anyMatch(method -> method.getName().equals("initializeFrom")
                && method.getNumberOfParams() == 1 && method.getParam(0).getType().describe().endsWith(".Tag"));
            for (var usage : methods) {
                var method = usage.getDeclaration();
                if (!method.getName().equals("initializeFrom") || method.getNumberOfParams() != 1 || method.isStatic()) continue;
                if (!method.getParam(0).getType().describe().endsWith(".Tag")) continue;
                if (own && !method.declaringType().getQualifiedName().equals(owner)) continue;
                var ast = method.toAst(com.github.javaparser.ast.body.MethodDeclaration.class);
                if (ast.isPresent()) {
                    CodeNode node = graph.catalog.find(ast.get());
                    if (node != null && node.body != null) { graph.root("initialization", node); setup.add(node); }
                }
            }
            if (!setup.isEmpty()) graph.edge("", "configured_initialization", owner, setup, setup.size() > 1,
                false, "Initialization override and supporting source setup", null);
        } catch (RuntimeException exception) {
            List<CodeNode> alternatives = graph.catalog.named("initializeFrom", 1).stream()
                .filter(node -> graph.catalog.possiblySubtype(owner, node.owner)).toList();
            for (CodeNode node : alternatives) graph.root("initialization", node);
            graph.edge("", "configured_initialization", owner, alternatives, true, true,
                "Initialization resolution failed; all supplied alternatives retained", null);
        }
    }

    void receiver(String owner) {
        var type = graph.catalog.types.get(owner);
        if (type == null || type.isInterface() || !receiverVisited.add(owner)) return;
        List<CodeNode> constructors = graph.catalog.constructors(owner, -1);
        for (CodeNode node : constructors) graph.root("supporting_initialization", node);
        graph.edge("", "receiver_construction", owner, constructors, constructors.size() != 1,
            constructors.isEmpty(), "Retain construction alternatives for input/collaborator receivers", null);
    }

    void properties(org.w3c.dom.Element binding, boolean step) {
        String owner = binding.getAttribute("implementation");
        if (!graph.catalog.types.containsKey(owner)) return;
        Set<String> setters = new TreeSet<>();
        var attributes = binding.getElementsByTagName("attribute");
        for (int i = 0; i < attributes.getLength(); i++) {
            setters.add(("set" + ((org.w3c.dom.Element) attributes.item(i)).getAttribute("name")).toLowerCase(java.util.Locale.ROOT));
        }
        if (step) setters.add("setcontext");
        else setters.addAll(List.of("addchild", "adddecorator", "addattributedecorator"));
        try {
            List<CodeNode> candidates = new ArrayList<>();
            for (var usage : graph.catalog.scope.solverFor(owner).solveType(owner).getAllMethods()) {
                var method = usage.getDeclaration();
                if (method.isStatic() || method.getNumberOfParams() != 1
                        || method.accessSpecifier() != com.github.javaparser.ast.AccessSpecifier.PUBLIC
                        || !setters.contains(method.getName().toLowerCase(java.util.Locale.ROOT))) continue;
                var ast = method.toAst(com.github.javaparser.ast.body.MethodDeclaration.class);
                if (ast.isPresent()) {
                    CodeNode node = graph.catalog.find(ast.get());
                    if (node != null && node.body != null) { graph.root("initialization", node); candidates.add(node); }
                }
            }
            if (!candidates.isEmpty()) graph.edge("", "configured_property_binding", owner, candidates, true, false,
                "XML/property or framework-context setter candidates retained; actual injection is established by the harness", null);
        } catch (RuntimeException exception) { graph.issues.add("Configured property binding could not be resolved: " + owner); }
    }

    void statics(String owner, String from) {
        var type = graph.catalog.types.get(owner);
        if (type == null) return;
        List<CodeNode> nodes = graph.catalog.members.get(owner).stream().filter(node -> node.kind.startsWith("static_")).toList();
        if (!nodes.isEmpty()) graph.edge(from, "static_initialization", owner, nodes, false, false, "Java class initialization", null);
        if (!staticVisited.add(owner)) return;
        try {
            for (var parent : type.getExtendedTypes()) statics(parent.resolve().asReferenceType().getQualifiedName(), from);
            for (var parent : type.getImplementedTypes()) statics(parent.resolve().asReferenceType().getQualifiedName(), from);
        } catch (RuntimeException exception) { graph.issues.add("Unresolved parent initialization: " + owner); }
    }

    void constructor(CodeNode node) {
        List<CodeNode> fields = graph.catalog.members.getOrDefault(node.owner, List.of()).stream()
            .filter(value -> value.kind.startsWith("instance_")).toList();
        if (!fields.isEmpty()) graph.edge(node.id, "instance_initialization", node.owner, fields, false, false, "Java instance initialization", null);
        if (node.anchor instanceof ConstructorDeclaration declaration
                && declaration.getBody().getStatements().stream().anyMatch(value -> value instanceof ExplicitConstructorInvocationStmt)) return;
        var type = graph.catalog.types.get(node.owner);
        if (type == null) { graph.issues.add("Parent construction needs runtime binding: " + node.owner); return; }
        if (type.getExtendedTypes().isEmpty()) {
            graph.external(node.id, "parent_constructor", "java.lang.Object.Object()", null, false, false, "Implicit super constructor");
            return;
        }
        try {
            String parent = type.getExtendedTypes().get(0).resolve().asReferenceType().getQualifiedName();
            if (!graph.catalog.types.containsKey(parent)) {
                graph.external(node.id, "parent_constructor", parent + ".<init>()", null, false,
                    !parent.startsWith("java."), "Parent constructor outside supplied source");
            } else {
                List<CodeNode> candidates = graph.catalog.constructors(parent, 0);
                graph.edge(node.id, "parent_constructor", parent, candidates, candidates.size() != 1,
                    candidates.isEmpty(), "Implicit parent no-argument construction", null);
            }
        } catch (RuntimeException exception) { graph.issues.add("Unresolved parent constructor: " + node.owner); }
    }
}
