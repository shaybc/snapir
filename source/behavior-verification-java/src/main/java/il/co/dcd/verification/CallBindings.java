package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import com.github.javaparser.resolution.declarations.ResolvedConstructorDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import java.util.*;

/** Bind call sites or retain every supplied candidate with an explicit unresolved edge. */
final class CallBindings {
    private final ReachableSlice graph;
    private final ImplicitCalls implicit;

    CallBindings(ReachableSlice graph) { this.graph = graph; implicit = new ImplicitCalls(graph, this); }

    void scan(Node site, CodeNode from) {
        if (site instanceof CallableDeclaration<?>) return;
        if (site instanceof TypeDeclaration<?>) {
            opaque(site, from);
            return;
        }
        implicit.scan(site, from);
        if (site instanceof MethodCallExpr call) {
            try {
                method(call.resolve(), call, from, call.getScope().map(Expression::isSuperExpr).orElse(false));
            } catch (RuntimeException exception) {
                graph.edge(from.id, "unresolved_call", call.getNameAsString(), graph.catalog.named(call.getNameAsString(), call.getArguments().size()),
                    true, true, "Unresolved call; supplied name/arity candidates may not bound the runtime target", site);
            }
        } else if (site instanceof ObjectCreationExpr creation) {
            try { constructor(creation.resolve(), creation, from); }
            catch (RuntimeException exception) {
                List<CodeNode> candidates = graph.catalog.nodes.values().stream().filter(node ->
                    node.anchor instanceof ConstructorDeclaration value && value.getParameters().size() == creation.getArguments().size()
                    || node.kind.equals("implicit_constructor") && creation.getArguments().isEmpty()).toList();
                graph.edge(from.id, "unresolved_construction", creation.getType().toString(), candidates, true, true,
                    "Unresolved construction; all supplied arity candidates retained", site);
            }
            if (creation.getAnonymousClassBody().isPresent()) opaque(creation, from);
        } else if (site instanceof ExplicitConstructorInvocationStmt invocation) {
            try { constructor(invocation.resolve(), invocation, from); }
            catch (RuntimeException exception) {
                graph.edge(from.id, "unresolved_construction", invocation.toString(),
                    graph.catalog.nodes.values().stream().filter(node -> node.kind.equals("constructor") || node.kind.equals("implicit_constructor")).toList(),
                    true, true, "Explicit this/super construction could not be resolved", site);
            }
        } else if (site instanceof MethodReferenceExpr reference) {
            try { method(reference.resolve(), reference, from, reference.getScope().isSuperExpr()); }
            catch (RuntimeException exception) {
                List<CodeNode> candidates = reference.getIdentifier().equals("new")
                    ? graph.catalog.nodes.values().stream().filter(node -> node.kind.equals("constructor") || node.kind.equals("implicit_constructor")).toList()
                    : graph.catalog.named(reference.getIdentifier(), -1);
                graph.edge(from.id, "unresolved_reference", reference.toString(), candidates, true, true,
                    "Method/constructor reference requires runtime binding", site);
            }
        } else if (site instanceof FieldAccessExpr || site instanceof NameExpr) {
            field(site, from);
        }
        for (Node child : site.getChildNodes()) scan(child, from);
    }

    private void method(ResolvedMethodDeclaration declaration, Node site, CodeNode from, boolean superCall) {
        bindMethod(declaration, site, from, superCall, site instanceof MethodReferenceExpr ? "method_reference" : "method_call");
    }

    void bindMethod(ResolvedMethodDeclaration declaration, Node site, CodeNode from, boolean superCall, String kind) {
        String signature = declaration.getQualifiedSignature();
        String owner = declaration.declaringType().getQualifiedName();
        var ast = declaration.toAst(MethodDeclaration.class);
        boolean exact = superCall || declaration.isStatic() || ast.map(value -> value.isPrivate() || value.isFinal()).orElse(false);
        List<CodeNode> targets = new ArrayList<>();
        if (ast.isPresent() && ast.get().getBody().isPresent()) {
            CodeNode target = graph.catalog.find(ast.get());
            if (target == null) {
                target = graph.catalog.add(ast.get(), ast.get().getBody().orElseThrow(), owner, signature, "method");
                graph.issues.add("Source declaring type was not fully indexed: " + owner);
            }
            targets.add(target);
        }
        if (!exact) targets.addAll(graph.catalog.dispatch(declaration));
        targets = targets.stream().distinct().toList();
        for (CodeNode target : targets) if (!declaration.isStatic()) graph.initialization.receiver(target.owner);
        boolean open = declaration.isAbstract();
        if (!targets.isEmpty()) {
            graph.edge(from.id, kind, signature,
                targets, !exact, open, exact ? "Resolved direct source call" : open
                    ? "Abstract dispatch: all supplied bodies retained; additional runtime implementations are not ruled out"
                    : "Runtime dispatch: every compatible supplied source body retained", site);
        }
        if (targets.isEmpty() && ast.isPresent() && declaration.isAbstract()) {
            graph.edge(from.id, "abstract_dispatch", signature, List.of(), true, true,
                "Abstract source call has no supplied executable target; runtime/configuration binding is unresolved", site);
        } else if (ast.isEmpty() || targets.isEmpty()) {
            graph.external(from.id, kind.startsWith("implicit_") ? kind : "external_call", signature, site, !exact && declaration.isAbstract(),
                !owner.startsWith("java.") && !owner.startsWith("javax.") && !owner.startsWith("org.w3c.") && !owner.startsWith("org.xml."),
                "Target outside supplied source; observable-boundary classification is deferred");
        }
        if (ast.isEmpty()) implicit.callbacks(declaration, site, from);
        if ((owner.startsWith("java.lang.reflect.") && (declaration.getName().equals("invoke") || declaration.getName().equals("newInstance")))
                || owner.equals("java.lang.Class") && (declaration.getName().equals("forName") || declaration.getName().equals("newInstance")
                    || declaration.getName().startsWith("getMethod") || declaration.getName().startsWith("getDeclaredMethod"))) {
            List<CodeNode> possible = graph.catalog.nodes.values().stream().filter(node -> node.body != null || node.kind.equals("implicit_constructor")).toList();
            graph.edge(from.id, "reflective_dispatch", signature, possible, true, true,
                "Reflection is not bounded by supplied evidence; all supplied code bodies retained", site);
        }
    }

    private void constructor(ResolvedConstructorDeclaration declaration, Node site, CodeNode from) {
        String owner = declaration.declaringType().getQualifiedName();
        List<CodeNode> targets = new ArrayList<>();
        var ast = declaration.toAst(ConstructorDeclaration.class);
        if (ast.isPresent()) {
            CodeNode target = graph.catalog.find(ast.get());
            if (target != null) targets.add(target);
        }
        if (targets.isEmpty()) targets.addAll(graph.catalog.constructors(owner, declaration.getNumberOfParams()));
        if (targets.isEmpty()) graph.external(from.id, "external_constructor", declaration.getQualifiedSignature(), site, false,
            !owner.startsWith("java.") && !owner.startsWith("javax.") && !owner.startsWith("org.w3c.") && !owner.startsWith("org.xml."), "Constructor outside supplied source");
        else graph.edge(from.id, "constructor_call", declaration.getQualifiedSignature(), targets, targets.size() > 1,
            false, "Resolved original construction", site);
        if (targets.isEmpty()) implicit.callbacks(declaration, site, from);
    }

    private void field(Node site, CodeNode from) {
        try {
            var declaration = site instanceof FieldAccessExpr value ? value.resolve() : ((NameExpr) site).resolve();
            if (!declaration.isField()) return;
            var field = declaration.asField();
            String owner = field.declaringType().getQualifiedName();
            graph.initialization.statics(owner, from.id);
            List<CodeNode> initializers = graph.catalog.members.getOrDefault(owner, List.of()).stream()
                .filter(node -> node.signature.equals(owner + "." + field.getName())).toList();
            if (!initializers.isEmpty()) graph.edge(from.id, "field_initialization", owner + "." + field.getName(), initializers,
                false, false, "Referenced field initializer", site);
        } catch (RuntimeException exception) {
            String name = site instanceof FieldAccessExpr value ? value.getNameAsString() : ((NameExpr) site).getNameAsString();
            List<CodeNode> possible = graph.catalog.nodes.values().stream().filter(node -> node.kind.contains("field_")
                && node.signature.endsWith("." + name)).toList();
            if (!possible.isEmpty()) graph.edge(from.id, "unresolved_field", name, possible, true, true,
                "Field binding unresolved; matching supplied initializers retained", site);
        }
    }

    private void opaque(Node declaration, CodeNode from) {
        List<CodeNode> retained = new ArrayList<>();
        String owner = from.owner + ".$local@" + declaration.getBegin().orElseThrow();
        for (MethodDeclaration method : declaration.findAll(MethodDeclaration.class)) {
            if (method.getBody().isPresent()) retained.add(graph.catalog.add(method, method.getBody().orElseThrow(), owner,
                owner + "." + method.getSignature(), "method"));
        }
        for (ConstructorDeclaration constructor : declaration.findAll(ConstructorDeclaration.class)) {
            retained.add(graph.catalog.add(constructor, constructor.getBody(), owner, owner + "." + constructor.getSignature(), "constructor"));
        }
        for (InitializerDeclaration initializer : declaration.findAll(InitializerDeclaration.class)) {
            retained.add(graph.catalog.add(initializer, initializer.getBody(), owner, owner + ".<initializer>",
                initializer.isStatic() ? "static_initializer" : "instance_initializer"));
        }
        for (FieldDeclaration field : declaration.findAll(FieldDeclaration.class)) for (VariableDeclarator variable : field.getVariables()) {
            variable.getInitializer().ifPresent(value -> retained.add(graph.catalog.add(value, value, owner,
                owner + "." + variable.getNameAsString(), field.isStatic() ? "static_field_initializer" : "instance_field_initializer")));
        }
        graph.edge(from.id, "local_type_binding", owner, retained, true, true,
            "Local/anonymous bodies retained conservatively; precise runtime binding is unresolved", declaration);
    }
}
