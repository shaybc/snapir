package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.ForEachStmt;
import com.github.javaparser.ast.stmt.TryStmt;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedMethodLikeDeclaration;
import com.github.javaparser.resolution.types.ResolvedType;
import java.util.*;

/** Java-defined resource/iteration/string calls and conservative library callback targets. */
final class ImplicitCalls {
    private final ReachableSlice graph;
    private final CallBindings bindings;

    ImplicitCalls(ReachableSlice graph, CallBindings bindings) { this.graph = graph; this.bindings = bindings; }

    void scan(Node site, CodeNode from) {
        if (site instanceof TryStmt statement) {
            for (Expression resource : statement.getResources()) {
                try {
                    ResolvedType type = resource instanceof VariableDeclarationExpr variables
                        ? variables.getVariable(0).getType().resolve() : resource.calculateResolvedType();
                    invoke(type, "close", resource, from, "implicit_resource_close");
                } catch (RuntimeException exception) { unknown("close", resource, from, "Resource close target could not be resolved"); }
            }
        } else if (site instanceof ForEachStmt loop) {
            try {
                ResolvedType iterable = loop.getIterable().calculateResolvedType();
                if (!iterable.isArray()) {
                    ResolvedMethodDeclaration iterator = invoke(iterable, "iterator", loop.getIterable(), from, "implicit_iterator");
                    invoke(iterator.getReturnType(), "hasNext", loop.getIterable(), from, "implicit_iterator_guard");
                    invoke(iterator.getReturnType(), "next", loop.getIterable(), from, "implicit_iterator_next");
                }
            } catch (RuntimeException exception) {
                for (String name : List.of("iterator", "hasNext", "next")) unknown(name, loop.getIterable(), from, "Iteration binding unresolved");
            }
        } else if (site instanceof BinaryExpr expression && expression.getOperator() == BinaryExpr.Operator.PLUS) {
            try {
                if (expression.calculateResolvedType().describe().equals("java.lang.String")) {
                    stringValue(expression.getLeft(), from); stringValue(expression.getRight(), from);
                }
            } catch (RuntimeException exception) { unknown("toString", expression, from, "String conversion binding unresolved"); }
        } else if (site instanceof MethodCallExpr call) {
            try {
                var method = call.resolve();
                if (method.declaringType().getQualifiedName().equals("java.lang.String") && method.getName().equals("valueOf")
                        && method.getNumberOfParams() == 1 && method.getParam(0).getType().describe().equals("java.lang.Object")) {
                    try { stringValue(call.getArgument(0), from); }
                    catch (RuntimeException exception) { unknown("toString", call.getArgument(0), from, "Object conversion binding unresolved"); }
                }
            } catch (RuntimeException ignored) { /* The explicit call is retained by CallBindings. */ }
        }
    }

    private ResolvedMethodDeclaration invoke(ResolvedType type, String name, Node site, CodeNode from, String kind) {
        var declaration = type.asReferenceType().getTypeDeclaration().orElseThrow();
        var selected = declaration.getAllMethods().stream().filter(value -> value.getName().equals(name)
            && value.getNoParams() == 0).map(value -> value.getDeclaration()).toList();
        if (selected.isEmpty()) throw new IllegalStateException("No implicit method: " + name);
        for (var method : selected) bindings.bindMethod(method, site, from, false, kind);
        return selected.get(0);
    }

    private void stringValue(Expression expression, CodeNode from) {
        ResolvedType type = expression.calculateResolvedType();
        if (type.isNull() || type.isPrimitive() || type.describe().equals("java.lang.String") || type.isArray()) return;
        if (!type.isReferenceType()) { unknown("toString", expression, from, "Unresolved generic string conversion"); return; }
        invoke(type, "toString", expression, from, "implicit_string_conversion");
        if (type.describe().equals("java.lang.Object")) unknown("toString", expression, from, "Object conversion may target types outside supplied evidence");
    }

    private void unknown(String name, Node site, CodeNode from, String reason) {
        graph.edge(from.id, "unresolved_implicit_call", name, graph.catalog.named(name, 0), true, true, reason, site);
    }

    void callbacks(ResolvedMethodLikeDeclaration method, Node site, CodeNode from) {
        List<Expression> arguments;
        if (site instanceof MethodCallExpr call) arguments = call.getArguments();
        else if (site instanceof ObjectCreationExpr creation) arguments = creation.getArguments();
        else return;
        for (int index = 0; index < arguments.size() && method.getNumberOfParams() > 0; index++) {
            try {
                ResolvedType type = method.getParam(Math.min(index, method.getNumberOfParams() - 1)).getType().erasure();
                if (type.isArray()) type = type.asArrayType().getComponentType();
                if (!type.isReferenceType()) continue;
                var declaration = type.asReferenceType().getTypeDeclaration().orElseThrow();
                String owner = declaration.getQualifiedName();
                if (graph.catalog.types.keySet().stream().noneMatch(candidate -> graph.catalog.possiblySubtype(candidate, owner))) continue;
                List<CodeNode> candidates = new ArrayList<>();
                for (var member : declaration.getAllMethods()) {
                    if (!member.getDeclaration().isStatic()) candidates.addAll(graph.catalog.dispatch(member.getDeclaration()));
                }
                if (!candidates.isEmpty()) graph.edge(from.id, "external_callback", method.getQualifiedSignature(), candidates,
                    true, true, "Library body is opaque; compatible supplied callback implementations retained", arguments.get(index));
            } catch (RuntimeException exception) {
                graph.issues.add("Library callback contract could not be resolved at " + from.signature + ":" + site.getBegin().orElseThrow().line);
            }
        }
    }
}
