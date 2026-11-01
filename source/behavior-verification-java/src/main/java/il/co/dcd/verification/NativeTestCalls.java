package il.co.dcd.verification;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import java.util.LinkedHashSet;

/** Record direct calls on explicitly typed receivers; do not guess unresolved helper APIs. */
final class NativeTestCalls {
    private NativeTestCalls() { }

    static void inspect(Document document, Element file, CompilationUnit unit) {
        for (var call : unit.findAll(MethodCallExpr.class)) {
            if (call.getScope().isEmpty()) {
                var owners = new LinkedHashSet<String>();
                var wildcardOwners = new LinkedHashSet<String>();
                for (var imported : unit.getImports()) {
                    if (!imported.isStatic()) continue;
                    String name = imported.getNameAsString();
                    if (imported.isAsterisk()) wildcardOwners.add(name);
                    else if (name.endsWith("." + call.getNameAsString()))
                        owners.add(name.substring(0, name.lastIndexOf('.')));
                }
                if (owners.isEmpty()) owners.addAll(wildcardOwners);
                if (owners.size() == 1) {
                    var entry = document.createElement("test-call");
                    entry.setAttribute("receiver_type", owners.iterator().next());
                    entry.setAttribute("method", call.getNameAsString());
                    entry.setAttribute("line", String.valueOf(call.getBegin().map(p -> p.line).orElse(0)));
                    entry.setAttribute("path", file.getAttribute("path"));
                    file.appendChild(entry);
                }
                continue;
            }
            var scope = call.getScope().get();
            String receiver = null;
            if (scope instanceof ObjectCreationExpr created) receiver = created.getTypeAsString();
            else {
                String name = scope instanceof NameExpr named ? named.getNameAsString() :
                    scope instanceof FieldAccessExpr field && field.getScope() instanceof ThisExpr ? field.getNameAsString() : null;
                if (name == null) {
                    String qualified = scope.toString();
                    if (qualified.matches("(?:[a-z_$][\\w$]*\\.)+[A-Z_$][\\w$]*")) receiver = qualified;
                    if (receiver == null) continue;
                }
                var candidates = new LinkedHashSet<String>();
                var callable = call.findAncestor(CallableDeclaration.class);
                if (!(scope instanceof FieldAccessExpr) && callable.isPresent()) {
                    for (Object item : callable.get().getParameters()) {
                        var parameter = (Parameter) item;
                        if (parameter.getNameAsString().equals(name)) candidates.add(parameter.getTypeAsString());
                    }
                    for (var variable : callable.get().findAll(VariableDeclarator.class))
                        if (variable.getNameAsString().equals(name)) candidates.add(variable.getTypeAsString());
                }
                if (candidates.isEmpty()) {
                    var owner = call.findAncestor(TypeDeclaration.class);
                    if (owner.isPresent()) for (Object item : owner.get().getFields()) {
                        var field = (FieldDeclaration) item;
                        for (var variable : field.getVariables())
                            if (variable.getNameAsString().equals(name)) candidates.add(variable.getTypeAsString());
                    }
                }
                if (candidates.size() == 1) receiver = candidates.iterator().next();
                else if (candidates.isEmpty() && name != null && Character.isUpperCase(name.charAt(0))) receiver = name;
            }
            if (receiver == null || receiver.equals("var")) continue;
            var entry = document.createElement("test-call");
            entry.setAttribute("receiver_type", receiver);
            entry.setAttribute("method", call.getNameAsString());
            entry.setAttribute("line", String.valueOf(call.getBegin().map(p -> p.line).orElse(0)));
            entry.setAttribute("path", file.getAttribute("path"));
            file.appendChild(entry);
        }
    }
}
