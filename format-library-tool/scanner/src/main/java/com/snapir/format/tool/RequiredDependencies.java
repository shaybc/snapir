package com.snapir.format.tool;

import com.github.javaparser.ast.*;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import com.github.javaparser.resolution.UnsolvedSymbolException;
import com.github.javaparser.resolution.declarations.*;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import java.util.*;

/** Conservative member reachability for one formatter, isolated from other formatter roots. */
final class RequiredDependencies {
    private static final Set<String> ENTRIES = Set.of("format", "unformat", "formatContext",
        "unformatContext", "formatField", "unformatField", "initializeFrom", "beforeFormatDo",
        "beforeUnformatDo", "addDecoration", "removeDecoration", "formatXmlAttributes", "unformatXmlAttributes");
    private final Map<String, Map<String, Object>> catalog;
    private final Map<String, TypeDeclaration<?>> declarations;
    private final Map<String, CombinedTypeSolver> solvers;
    private final Map<String, Map<String, Object>> scope = new TreeMap<>();
    private final Deque<Work> pending = new ArrayDeque<>();
    private final Set<String> seen = new HashSet<>(), initialized = new HashSet<>();
    private final Set<String> defaultConstructors = new HashSet<>();
    private record Work(Node node, String owner, String receiver, String label) { }

    RequiredDependencies(Map<String, Map<String, Object>> catalog, Map<String, TypeDeclaration<?>> declarations,
                         Map<String, CombinedTypeSolver> solvers) {
        this.catalog = catalog; this.declarations = declarations; this.solvers = solvers;
    }

    @SuppressWarnings("unchecked")
    Map<String, Map<String, Object>> analyze(String root, boolean foundation) {
        addType(root, root);
        initialize(root, true);
        TypeDeclaration<?> declaration = declarations.get(root);
        if (declaration instanceof ClassOrInterfaceDeclaration type) {
            try {
                List<String> hierarchy = new ArrayList<>(); hierarchy.add(root);
                hierarchy.addAll((Collection<String>) catalog.get(root).get("ancestors"));
                for (String name : hierarchy) {
                    if (!(declarations.get(name) instanceof ClassOrInterfaceDeclaration source)) continue;
                    for (var method : source.resolve().getDeclaredMethods()) {
                        if (ENTRIES.contains(method.getName()) || foundation
                                && method.accessSpecifier() != com.github.javaparser.ast.AccessSpecifier.PRIVATE) {
                            enqueueMethod(method, root, false);
                        }
                    }
                }
            } catch (RuntimeException error) { problem(root, "Entry methods", root, error, declaration); }
            for (var constructor : type.getConstructors())
                enqueueConstructor(constructor, root, root);
            if (type.getConstructors().isEmpty()) defaultSuper(root, root);
        }
        if (foundation && declaration != null)
            for (var field : declaration.getFields()) enqueue(field, root, root, "foundation field " + field.getVariables());
        while (!pending.isEmpty()) {
            Work work = pending.removeFirst();
            if (!seen.add(work.owner + "|" + work.receiver + "|" + work.label)) continue;
            members(work.owner).add(work.label);
            System.out.println("Inspecting member " + work.owner + ": " + work.label);
            System.out.flush();
            inspect(work.node, work.node, work.owner, work.receiver);
        }
        return scope;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> record(String owner) {
        if (!catalog.containsKey(owner)) return null;
        return scope.computeIfAbsent(owner, key -> {
            var result = new LinkedHashMap<>(catalog.get(owner));
            result.put("dependencies", new TreeSet<String>((Collection<String>) result.get("ancestors")));
            result.put("issues", new ArrayList<String>((Collection<String>) result.get("issues")));
            result.put("unresolved_dependencies", new TreeSet<String>((Collection<String>) result.get("unresolved_dependencies")));
            result.put("required_members", new TreeSet<String>());
            result.put("dynamic_calls", new TreeSet<String>());
            result.put("dependency_status", "analyzed");
            return result;
        });
    }

    @SuppressWarnings("unchecked")
    private Set<String> members(String owner) { return (Set<String>) record(owner).get("required_members"); }

    @SuppressWarnings("unchecked")
    private void addType(String owner, String target) {
        if (record(owner) != null && !owner.equals(target))
            ((Set<String>) record(owner).get("dependencies")).add(target);
        var entry = record(target);
        if (entry != null)
            for (String ancestor : (Collection<String>) entry.get("ancestors"))
                if (!ancestor.equals(target) && catalog.containsKey(ancestor)) record(ancestor);
    }

    private void enqueue(Node node, String owner, String receiver, String label) {
        record(owner);
        pending.addLast(new Work(node, owner, receiver, label));
    }

    @SuppressWarnings("unchecked")
    private void initialize(String owner, boolean instance) {
        if (!declarations.containsKey(owner)) return;
        if (instance) initialize(owner, false);
        if (!initialized.add(owner + ":" + instance)) return;
        TypeDeclaration<?> declaration = declarations.get(owner);
        record(owner);
        for (var field : declaration.getFields())
            if (field.isStatic() != instance)
                for (var variable : field.getVariables())
                    if (variable.getInitializer().isPresent())
                        enqueue(variable, owner, owner, "field " + variable.getNameAsString());
        for (var initializer : declaration.getMembers())
            if (initializer instanceof InitializerDeclaration block && block.isStatic() != instance)
                enqueue(block, owner, owner, "initializer " + block.getRange().orElse(null));
        if (!instance && declaration instanceof EnumDeclaration enumeration)
            for (var constant : enumeration.getEntries()) enqueue(constant, owner, owner, "enum " + constant.getNameAsString());
        for (String ancestor : (Collection<String>) catalog.get(owner).get("ancestors")) {
            if (!declarations.containsKey(ancestor)) continue;
            var parent = declarations.get(ancestor);
            if (parent instanceof ClassOrInterfaceDeclaration type && !type.isInterface()) {
                initialize(ancestor, instance);
            }
        }
    }

    private void enqueueConstructor(ConstructorDeclaration constructor, String owner, String receiver) {
        enqueue(constructor, owner, receiver, "constructor " + constructor.getSignature());
        var statements = constructor.getBody().getStatements();
        if (statements.isEmpty() || !(statements.get(0) instanceof ExplicitConstructorInvocationStmt))
            defaultSuper(owner, receiver);
    }

    private void defaultSuper(String owner, String receiver) {
        if (!defaultConstructors.add(owner + "|" + receiver)) return;
        if (!(declarations.get(owner) instanceof ClassOrInterfaceDeclaration type) || type.getExtendedTypes().isEmpty()) return;
        try {
            String parent = type.getExtendedTypes().get(0).resolve().asReferenceType().getQualifiedName();
            if (!(declarations.get(parent) instanceof ClassOrInterfaceDeclaration source)) return;
            if (source.getConstructors().isEmpty()) defaultSuper(parent, receiver);
            else source.getConstructors().stream().filter(value -> value.getParameters().isEmpty())
                .forEach(value -> enqueueConstructor(value, parent, receiver));
        } catch (RuntimeException error) { problem(owner, "Superclass constructor", owner, error, type); }
    }

    @SuppressWarnings("unchecked")
    private void enqueueMethod(ResolvedMethodDeclaration method, String receiver, boolean explicitSuper) {
        String owner = method.declaringType().getQualifiedName();
        if (!explicitSuper && !method.isStatic() && catalog.containsKey(receiver)
                && (receiver.equals(owner) || ((Collection<String>) catalog.get(receiver).get("ancestors")).contains(owner))) {
            List<String> hierarchy = new ArrayList<>(); hierarchy.add(receiver);
            hierarchy.addAll((Collection<String>) catalog.get(receiver).get("ancestors"));
            String signature = method.getSignature();
            String methodName = method.getName();
            for (String candidate : hierarchy) {
                if (!(declarations.get(candidate) instanceof ClassOrInterfaceDeclaration type)) continue;
                var override = type.resolve().getDeclaredMethods().stream()
                    .filter(value -> value.getName().equals(methodName) && value.getSignature().equals(signature)
                        && !value.isAbstract()).findFirst();
                if (override.isPresent()) { method = override.get(); owner = candidate; break; }
            }
        }
        if (!catalog.containsKey(owner)) return; // Binary bodies remain outside supplied source.
        initialize(owner, false);
        var ast = method.toAst(MethodDeclaration.class);
        if (ast.isPresent() && ast.get().getBody().isPresent())
            enqueue(ast.get(), owner, receiver, method.getQualifiedSignature());
        else
            ((Set<String>) record(owner).get("dynamic_calls")).add(method.getQualifiedSignature());
    }

    private void field(ResolvedValueDeclaration value, String consumer, String receiver) {
        if (value.isField()) {
            var field = value.asField();
            String owner = field.declaringType().getQualifiedName();
            addType(consumer, owner);
            if (catalog.containsKey(owner)) {
                initialize(owner, field.isStatic() ? false : true);
                var ast = field.toAst();
                ast.ifPresent(node -> {
                    if (node instanceof VariableDeclarator variable)
                        enqueue(variable, owner, receiver, "field " + field.getName());
                    else if (node instanceof FieldDeclaration declaration)
                        declaration.getVariables().stream().filter(v -> v.getNameAsString().equals(field.getName()))
                            .forEach(variable -> enqueue(variable, owner, receiver, "field " + field.getName()));
                });
            }
        } else if (value.isEnumConstant()) {
            String owner = value.asEnumConstant().getType().asReferenceType().getQualifiedName();
            addType(consumer, owner); initialize(owner, false);
        }
    }

    private void inspect(Node node, Node start, String owner, String receiver) {
        if (node != start && (node instanceof CallableDeclaration<?> || node instanceof TypeDeclaration<?>
                || node instanceof FieldDeclaration || node instanceof InitializerDeclaration)) return;
        var solver = solvers.get((String) catalog.get(owner).get("project"));
        if (node instanceof ClassOrInterfaceType type) {
            if (type.getParentNode().filter(parent -> parent instanceof ClassOrInterfaceType outer
                    && outer.getScope().orElse(null) == type).isPresent()) return;
            try {
                var resolved = type.resolve();
                if (resolved.isReferenceType()) addType(owner, resolved.asReferenceType().getQualifiedName());
            }
            catch (RuntimeException error) { problem(owner, "Type", type.toString(), error, node); }
        } else if (node instanceof FieldAccessExpr access) {
            try {
                // A qualified type used as a static-call scope is not a field (java.util.Calendar).
                if (solver.tryToSolveType(access.toString()).isSolved()) {
                    addType(owner, access.toString()); return;
                }
                field(access.resolve(), owner, receiver);
            } catch (RuntimeException error) { problem(owner, "Field", access.toString(), error, node); }
        } else if (node instanceof NameExpr name) {
            try { field(name.resolve(), owner, receiver); }
            catch (RuntimeException error) {
                boolean qualifier = name.getParentNode().filter(parent ->
                    parent instanceof MethodCallExpr call && call.getScope().orElse(null) == name
                    || parent instanceof FieldAccessExpr access && access.getScope() == name).isPresent();
                if (!qualifier) problem(owner, "Name", name.toString(), error, node);
            }
        } else if (node instanceof MethodCallExpr call) {
            try {
                var method = call.resolve();
                addType(owner, method.declaringType().getQualifiedName());
                String actualReceiver = receiver;
                boolean superCall = call.getScope().filter(Expression::isSuperExpr).isPresent();
                if (call.getScope().isPresent() && !call.getScope().get().isThisExpr() && !superCall && !method.isStatic()) {
                    var type = call.getScope().get().calculateResolvedType();
                    if (type.isReferenceType()) actualReceiver = type.asReferenceType().getQualifiedName();
                }
                enqueueMethod(method, actualReceiver, superCall);
            } catch (RuntimeException error) { problem(owner, "Call", call.getNameAsString(), error, node); }
        } else if (node instanceof ObjectCreationExpr creation) {
            try {
                var constructor = creation.resolve();
                String target = constructor.declaringType().getQualifiedName();
                addType(owner, target); initialize(target, true);
                var ast = constructor.toAst(ConstructorDeclaration.class);
                if (ast.isPresent()) enqueueConstructor(ast.get(), target, target);
                else defaultSuper(target, target);
            } catch (RuntimeException error) { problem(owner, "Constructor", creation.getTypeAsString(), error, node); }
        } else if (node instanceof ExplicitConstructorInvocationStmt invocation) {
            try {
                var constructor = invocation.resolve();
                String target = constructor.declaringType().getQualifiedName();
                addType(owner, target);
                var ast = constructor.toAst(ConstructorDeclaration.class);
                if (ast.isPresent()) enqueueConstructor(ast.get(), target, receiver);
            } catch (RuntimeException error) { problem(owner, "Constructor delegation", invocation.toString(), error, node); }
        } else if (node instanceof MethodReferenceExpr reference) {
            try {
                var method = reference.resolve();
                addType(owner, method.declaringType().getQualifiedName());
                enqueueMethod(method, receiver, false);
            } catch (RuntimeException error) { problem(owner, "Method reference", reference.toString(), error, node); }
        }
        for (Node child : node.getChildNodes()) inspect(child, start, owner, receiver);
    }

    @SuppressWarnings("unchecked")
    private void problem(String owner, String kind, String subject, RuntimeException error, Node node) {
        var entry = record(owner);
        ((List<String>) entry.get("issues")).add(kind + " unresolved: " + subject + ": " + error.getMessage());
        String symbol = null;
        for (Throwable cause = error; cause != null; cause = cause.getCause())
            if (cause instanceof UnsolvedSymbolException unresolved) { symbol = unresolved.getName(); break; }
        if (node instanceof MethodCallExpr call && call.getScope().orElse(null) instanceof NameExpr variable) {
            try {
                var value = variable.resolve();
                try { value.getType(); }
                catch (RuntimeException typeError) {
                    for (Throwable cause = typeError; cause != null; cause = cause.getCause())
                        if (cause instanceof UnsolvedSymbolException unresolved) { symbol = unresolved.getName(); break; }
                }
            } catch (RuntimeException ignored) { /* A static class qualifier is not a value declaration. */ }
        }
        if (symbol == null || symbol.isBlank()) symbol = kind + " dependency: " + subject;
        String simple = symbol.replaceAll("<.*>", "").split("\\.")[0];
        var unit = node.findCompilationUnit();
        if (unit.isPresent())
            for (var imported : unit.get().getImports())
                if (!imported.isStatic() && !imported.isAsterisk() && imported.getName().getIdentifier().equals(simple)) {
                    symbol = imported.getNameAsString(); break;
                }
        ((Set<String>) entry.get("unresolved_dependencies")).add(symbol);
    }
}
