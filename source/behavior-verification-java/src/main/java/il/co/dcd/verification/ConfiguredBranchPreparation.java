package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Prove only pure initialization predicates and private fields written exclusively during setup. */
final class ConfiguredBranchPreparation {
    private ConfiguredBranchPreparation() { }

    static Map<String, Object> inspect(Element input, SourceCatalog catalog) {
        Map<String, Object> result = new TreeMap<>();
        for (Element item : BoundaryValues.children(input, "item")) {
            if (!item.getAttribute("kind").equals("branch") || !Set.of("if", "short_circuit").contains(item.getAttribute("detail"))) continue;
            CodeNode owner = catalog.nodes.get(item.getAttribute("code_node_id"));
            if (owner == null || !(owner.anchor instanceof MethodDeclaration method)) continue;
            Node site = owner.anchor.findAll(Node.class).stream().filter(n -> ConfigurationPreparation.sameSite(n, item)).findFirst().orElse(null);
            Expression condition = item.getAttribute("detail").equals("short_circuit") && site instanceof BinaryExpr binary
                ? binary.getLeft() : site instanceof IfStmt stmt ? stmt.getCondition() : null;
            if (condition == null) continue;
            var type = catalog.types.get(owner.owner);
            if (type == null) continue;
            var initializers = type.getMethodsByName("initializeFrom").stream().filter(m -> m.getParameters().size() == 1 && m.getBody().isPresent()).toList();
            if (initializers.size() != 1) continue;
            var init = initializers.get(0);
            CodeNode initNode = catalog.find(init);
            if (initNode == null || BoundaryValues.children(input, "edge").stream().anyMatch(edge ->
                BoundaryValues.children(edge, "candidate").stream().anyMatch(c -> c.getAttribute("id").equals(initNode.id))
                    && (!edge.getAttribute("from_id").isEmpty() || !edge.getAttribute("kind").equals("configured_initialization")))) continue;
            String getter = getter(init, catalog);
            if (getter == null) continue;
            var bindings = ConfigurationPreparation.components(input).stream().filter(b -> b.getAttribute("implementation").equals(owner.owner)).toList();
            if (bindings.isEmpty()) continue;
            Set<String> outcomes = new TreeSet<>();
            boolean supported = true;
            for (Element binding : bindings) {
                @SuppressWarnings("unchecked") Map<String, String> attributes = (Map<String, String>)(Map<?, ?>)
                    BoundaryValues.read(BoundaryValues.child(binding, "attributes"));
                var values = new StaticConstantValues(init, init.getParameter(0).getNameAsString(), getter, attributes);
                Object value;
                if (method == init) value = values.value(condition);
                else {
                    Map<String, Object> fields = frozenFields(type, init, values);
                    value = new StaticConstantValues(method).withFields(fields).value(condition);
                }
                if (!(value instanceof Boolean flag)) { supported = false; break; }
                outcomes.add(value.toString());
            }
            if (supported && outcomes.size() == 1) result.put(item.getAttribute("id"), Map.of(
                "allowed_outcomes", new ArrayList<>(outcomes), "rule", "pure_tag_setup_or_private_setup_only_field",
                "source_identity", owner.source.getAttribute("identity"), "source_hash", owner.source.getAttribute("hash"),
                "code_node_id", owner.id, "condition", condition.toString(), "occurrences", bindings.size()));
        }
        return result;
    }

    private static String getter(MethodDeclaration init, SourceCatalog catalog) {
        try {
            String tag = init.getParameter(0).getType().resolve().describe();
            var type = catalog.types.get(tag);
            if (type == null || type.getExtendedTypes().size() > 0) return null;
            String parameter = init.getParameter(0).getNameAsString();
            String getter = null;
            for (NameExpr name : init.findAll(NameExpr.class)) {
                if (!name.getNameAsString().equals(parameter)) continue;
                if (!(name.getParentNode().orElse(null) instanceof MethodCallExpr call)) return null;
                if (call.getScope().orElse(null) == name && call.getArguments().size() == 1 && call.getArgument(0).isStringLiteralExpr()) {
                    var methods = type.getMethodsByName(call.getNameAsString());
                    if (methods.size() != 1 || !pureMapGetter(methods.get(0), type)) return null;
                    if (getter != null && !getter.equals(call.getNameAsString())) return null;
                    getter = call.getNameAsString();
                } else if (call.getScope().filter(Expression::isSuperExpr).isPresent()) {
                    // Forwarding to an empty base initializer cannot mutate this Tag snapshot.
                    var target = call.resolve().toAst(MethodDeclaration.class).orElse(null);
                    if (target == null || target.getBody().isEmpty() || !target.getBody().get().isEmpty()) return null;
                } else return null;
            }
            return getter;
        } catch (RuntimeException unsupported) { return null; }
    }

    private static boolean pureMapGetter(MethodDeclaration method, ClassOrInterfaceDeclaration type) {
        if (method.getParameters().size() != 1 || method.getBody().isEmpty() || method.getBody().get().getStatements().size() != 1) return false;
        var statement = method.getBody().get().getStatement(0);
        if (!(statement instanceof ReturnStmt ret) || ret.getExpression().isEmpty() || !(ret.getExpression().get() instanceof MethodCallExpr call)
            || !call.getNameAsString().equals("get") || call.getArguments().size() != 1
            || !call.getArgument(0).isNameExpr() || !call.getArgument(0).asNameExpr().getNameAsString().equals(method.getParameter(0).getNameAsString())
            || call.getScope().isEmpty() || !call.getScope().get().isNameExpr()) return false;
        var field = type.getFieldByName(call.getScope().get().asNameExpr().getNameAsString());
        if (field.isEmpty() || !field.get().isPrivate() || !field.get().isFinal() || field.get().isStatic()
            || type.getMembers().stream().anyMatch(m -> m instanceof InitializerDeclaration)) return false;
        String map = call.getScope().get().asNameExpr().getNameAsString();
        var constructors = type.getConstructors().stream().filter(c -> c.getParameters().size() == 1).toList();
        if (constructors.size() != 1 || constructors.get(0).getBody().getStatements().size() != 1
            || !constructors.get(0).getBody().getStatement(0).toString().replaceAll("\\s+", "").equals(
                "this." + map + ".putAll(" + constructors.get(0).getParameter(0).getNameAsString() + ");")
            || field.get().getVariables().size() != 1 || field.get().getVariable(0).getInitializer().isEmpty()
            || !field.get().getVariable(0).getInitializer().get().toString().replaceAll("\\s+", "").equals("newHashMap<>()")) return false;
        try { return call.resolve().declaringType().getQualifiedName().equals("java.util.Map")
            && field.get().getVariable(0).getInitializer().get().asObjectCreationExpr().resolve().declaringType().getQualifiedName().equals("java.util.HashMap"); }
        catch (RuntimeException unresolved) { return false; }
    }

    private static Map<String, Object> frozenFields(ClassOrInterfaceDeclaration type, MethodDeclaration init, StaticConstantValues values) {
        Map<String, Object> result = new HashMap<>();
        for (FieldDeclaration field : type.getFields()) for (var variable : field.getVariables()) {
            if (!field.isPrivate() || field.isStatic() || !variable.getType().asString().equals("boolean") || variable.getInitializer().isEmpty()) continue;
            if (type.findAll(ThisExpr.class).stream().anyMatch(t -> !(t.getParentNode().orElse(null) instanceof FieldAccessExpr)
                && !(t.getParentNode().orElse(null) instanceof ReturnStmt && t.findAncestor(MethodDeclaration.class).orElse(null) == init))) continue;
            if (type.findAll(MethodCallExpr.class).stream().anyMatch(c -> Set.of("getDeclaredField", "getField", "forName").contains(c.getNameAsString()))) continue;
            String name = variable.getNameAsString();
            var writes = type.findAll(AssignExpr.class).stream().filter(a -> fieldName(a.getTarget()).equals(name)).toList();
            if (writes.stream().anyMatch(a -> a.findAncestor(MethodDeclaration.class).orElse(null) != init)
                || !type.getConstructors().isEmpty() || !type.getMembers().stream().filter(m -> m instanceof InitializerDeclaration).toList().isEmpty()) continue;
            Object initial = new StaticConstantValues(null).value(variable.getInitializer().get());
            if (!(initial instanceof Boolean)) continue;
            Object current = initial;
            for (AssignExpr write : writes) {
                if (write.getOperator() != AssignExpr.Operator.ASSIGN) { current = StaticConstantValues.UNKNOWN; break; }
                if (write.getTarget().isFieldAccessExpr() && !write.getTarget().asFieldAccessExpr().getScope().isThisExpr()) {
                    current = StaticConstantValues.UNKNOWN; break;
                }
                if (write.getTarget().isNameExpr()) {
                    try { if (!write.getTarget().asNameExpr().resolve().isField()) { current = StaticConstantValues.UNKNOWN; break; } }
                    catch (RuntimeException unresolved) { current = StaticConstantValues.UNKNOWN; break; }
                }
                Object enabled = true;
                Node child = write;
                for (Node parent = write.getParentNode().orElse(null); parent != null && parent != init; child = parent, parent = parent.getParentNode().orElse(null)) {
                    if (parent instanceof IfStmt branch) {
                        Object flag = values.value(branch.getCondition());
                        if (!(flag instanceof Boolean)) { enabled = StaticConstantValues.UNKNOWN; break; }
                        boolean then = branch.getThenStmt() == child;
                        if ((Boolean)flag != then) enabled = false;
                    } else if (!(parent instanceof ExpressionStmt || parent instanceof BlockStmt)) { enabled = StaticConstantValues.UNKNOWN; break; }
                }
                if (enabled == StaticConstantValues.UNKNOWN) { current = enabled; break; }
                if (Boolean.TRUE.equals(enabled)) current = values.value(write.getValue());
            }
            if (current instanceof Boolean) result.put(name, current);
        }
        return result;
    }

    private static String fieldName(Expression expression) {
        if (expression instanceof NameExpr name) return name.getNameAsString();
        if (expression instanceof FieldAccessExpr field) return field.getNameAsString();
        return "";
    }
}
