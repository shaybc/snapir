package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import java.util.*;

/** Index supplied declarations; only graph-reachable bodies are emitted as slice evidence. */
final class SourceCatalog {
    final SourceScope scope;
    final Map<String, ClassOrInterfaceDeclaration> types = new TreeMap<>();
    final Map<String, CodeNode> nodes = new TreeMap<>();
    final Map<String, List<CodeNode>> members = new TreeMap<>();
    final List<String> problems = new ArrayList<>();
    private final Map<String, Boolean> subtypes = new HashMap<>();
    private final Map<String, List<CodeNode>> dispatches = new HashMap<>();

    SourceCatalog(SourceScope scope) {
        this.scope = scope;
        for (String name : scope.typeNames) {
            try {
                ClassOrInterfaceDeclaration type = scope.solverFor(name).solveType(name).toAst(ClassOrInterfaceDeclaration.class).orElseThrow();
                scope.bind(type);
                types.put(name, type);
                List<CodeNode> bodies = new ArrayList<>();
                members.put(name, bodies);
                for (BodyDeclaration<?> member : type.getMembers()) {
                    if (member instanceof MethodDeclaration method) {
                        String signature;
                        try { signature = method.resolve().getQualifiedSignature(); }
                        catch (RuntimeException unresolved) { signature = name + "." + method.getSignature(); }
                        bodies.add(add(method, method.getBody().orElse(null), name, signature, "method"));
                    } else if (member instanceof ConstructorDeclaration constructor) {
                        bodies.add(add(constructor, constructor.getBody(), name, name + "." + constructor.getSignature(), "constructor"));
                    } else if (member instanceof InitializerDeclaration initializer) {
                        String kind = initializer.isStatic() ? "static_initializer" : "instance_initializer";
                        bodies.add(add(initializer, initializer.getBody(), name, name + ".<" + kind + ">:" + initializer.getBegin().orElseThrow().line, kind));
                    } else if (member instanceof FieldDeclaration field) {
                        for (VariableDeclarator variable : field.getVariables()) {
                            bodies.add(add(variable, null, name, name + "." + variable.getNameAsString(),
                                type.isInterface() || field.isStatic() ? "static_field_default" : "instance_field_default"));
                            if (variable.getInitializer().isPresent()) {
                                Node expression = variable.getInitializer().orElseThrow();
                                bodies.add(add(expression, expression, name, name + "." + variable.getNameAsString(),
                                    type.isInterface() || field.isStatic() ? "static_field_initializer" : "instance_field_initializer"));
                            }
                        }
                    }
                }
                if (!type.isInterface() && type.getConstructors().isEmpty()) {
                    bodies.add(add(type.getName(), null, name, name + ".<init>()", "implicit_constructor"));
                }
            } catch (RuntimeException exception) {
                problems.add("Source type could not be indexed: " + name + ": " + exception.getMessage());
            }
        }
    }

    CodeNode add(Node anchor, Node body, String owner, String signature, String kind) {
        CodeNode result = new CodeNode(scope, anchor, body, owner, signature, kind);
        nodes.put(result.id, result);
        dispatches.clear();
        return result;
    }

    CodeNode find(Node node) {
        scope.bind(node);
        var source = scope.evidence(node.findCompilationUnit().orElseThrow());
        return nodes.values().stream().filter(value -> value.source.getAttribute("identity").equals(source.getAttribute("identity"))
            && value.anchor.getRange().equals(node.getRange())).findFirst().orElse(null);
    }

    List<CodeNode> constructors(String owner, int arity) {
        return members.getOrDefault(owner, List.of()).stream().filter(node ->
            node.kind.equals("implicit_constructor") ? arity < 1 : node.anchor instanceof ConstructorDeclaration method
                && (arity < 0 || method.getParameters().size() == arity || method.getParameters().stream().anyMatch(value -> value.isVarArgs()))).toList();
    }

    List<CodeNode> named(String name, int arity) {
        return nodes.values().stream().filter(node -> node.anchor instanceof MethodDeclaration method && node.body != null
            && method.getNameAsString().equals(name) && (arity < 0 || method.getParameters().size() == arity
            || method.getParameters().stream().anyMatch(value -> value.isVarArgs()))).toList();
    }

    /** Unknown subtype relationships are retained as candidates, never discarded. */
    boolean possiblySubtype(String candidate, String parent) {
        if (candidate.equals(parent)) return true;
        String key = candidate + "->" + parent;
        if (subtypes.containsKey(key)) return subtypes.get(key);
        try {
            boolean result = scope.solverFor(candidate).solveType(candidate).getAllAncestors().stream().anyMatch(type -> type.getQualifiedName().equals(parent));
            subtypes.put(key, result);
            return result;
        } catch (RuntimeException exception) { subtypes.put(key, true); return true; }
    }

    List<CodeNode> dispatch(ResolvedMethodDeclaration declaration) {
        String key = declaration.getQualifiedSignature();
        if (dispatches.containsKey(key)) return dispatches.get(key);
        List<CodeNode> result = new ArrayList<>();
        for (CodeNode node : named(declaration.getName(), declaration.getNumberOfParams())) {
            MethodDeclaration method = (MethodDeclaration) node.anchor;
            if (method.isStatic() || method.isPrivate() || !possiblySubtype(node.owner, declaration.declaringType().getQualifiedName())) continue;
            try {
                var candidate = method.resolve();
                boolean equal = true;
                for (int i = 0; i < declaration.getNumberOfParams(); i++) {
                    if (!compatible(candidate.getParam(i).getType(), declaration.getParam(i).getType())) equal = false;
                }
                if (equal) result.add(node);
            } catch (RuntimeException exception) { result.add(node); }
        }
        dispatches.put(key, result);
        return result;
    }

    private boolean compatible(com.github.javaparser.resolution.types.ResolvedType left,
                               com.github.javaparser.resolution.types.ResolvedType right) {
        if (left.isTypeVariable() || right.isTypeVariable() || left.isWildcard() || right.isWildcard()) return true;
        if (left.isArray() && right.isArray()) return compatible(left.asArrayType().getComponentType(), right.asArrayType().getComponentType());
        if (left.isReferenceType() && right.isReferenceType()) return left.asReferenceType().getQualifiedName().equals(right.asReferenceType().getQualifiedName());
        return left.describe().equals(right.describe());
    }
}
