package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import java.util.Set;

/** Composition owns decorator registration/traversal; basic elements retain their own behavior. */
final class BasicElementChecklist {
    private static final Set<String> HOOKS = Set.of(
        "applyDecorators", "removeDecorators", "addDecorator", "addAttributeDecorator");
    private static final Set<String> DECORATOR_TYPES = Set.of("FormatDecoratorHolder", "AttributeXmlFormatDecoratorImpl");

    private BasicElementChecklist() { }

    static boolean owner(CodeNode node) {
        if (node.anchor instanceof MethodDeclaration method && HOOKS.contains(method.getNameAsString())) return true;
        return node.anchor.findAncestor(FieldDeclaration.class).map(field ->
            field.getElementType().findAll(com.github.javaparser.ast.type.ClassOrInterfaceType.class).stream()
                .anyMatch(type -> DECORATOR_TYPES.contains(type.getNameAsString()))).orElse(false);
    }

    static boolean traversal(Node node) {
        if (!(node instanceof ForEachStmt || node instanceof ForStmt || node instanceof WhileStmt)) return false;
        return node.findAll(MethodCallExpr.class).stream().anyMatch(call ->
            Set.of("addDecoration", "removeDecoration", "formatXmlAttributes").contains(call.getNameAsString())
                && call.getScope().isPresent() && !call.getScope().orElseThrow().isThisExpr()
                && !call.getScope().orElseThrow().isSuperExpr());
    }

    static boolean item(Node node) {
        if (node instanceof MethodCallExpr call) return HOOKS.contains(call.getNameAsString());
        if (node instanceof AssignExpr assignment) return item(assignment.getValue());
        if (node instanceof VariableDeclarator variable) return variable.getInitializer().map(BasicElementChecklist::item).orElse(false);
        if (node instanceof ReturnStmt statement) return statement.getExpression().map(BasicElementChecklist::item).orElse(false);
        return false;
    }

    static boolean call(CodeNode owner, Node site) {
        if (owner(owner) || item(site)) return true;
        for (Node parent = site; parent != null && parent != owner.anchor; parent = parent.getParentNode().orElse(null)) {
            if (traversal(parent)) return true;
        }
        return false;
    }
}
