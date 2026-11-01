package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import java.util.List;

/** Enumerate syntax without guessing observable significance or evaluating branch conditions. */
final class ChecklistSyntax {
    private final ParserChecklist checklist;
    ChecklistSyntax(ParserChecklist checklist) { this.checklist = checklist; }

    void scan(Node site, CodeNode owner) {
        if (site instanceof CallableDeclaration<?> || site instanceof TypeDeclaration<?>) return;
        if (site instanceof LiteralExpr literal) literal(literal, owner);
        if (site instanceof IfStmt value) branch(owner, site, "if", value.getCondition().toString());
        else if (site instanceof ConditionalExpr value) branch(owner, site, "ternary", value.getCondition().toString());
        else if (site instanceof SwitchStmt value) branch(owner, site, "switch", value.getSelector().toString());
        else if (site instanceof SwitchExpr value) branch(owner, site, "switch", value.getSelector().toString());
        else if (site instanceof SwitchEntry value) {
            checklist.add(owner, site, "branch", "switch_case")
                .property("condition", value.getLabels().isEmpty() ? "default" : value.getLabels().toString())
                .property("includes_default", Boolean.toString(value.isDefault()));
            value.getGuard().ifPresent(guard -> branch(owner, guard, "switch_guard", guard.toString()));
        }
        else if (site instanceof ForStmt value) branch(owner, site, "for_guard", value.getCompare().map(Node::toString).orElse("true (implicit)"));
        else if (site instanceof ForEachStmt value) branch(owner, site, "foreach", value.getIterable().toString());
        else if (site instanceof WhileStmt value) branch(owner, site, "while_guard", value.getCondition().toString());
        else if (site instanceof DoStmt value) branch(owner, site, "do_guard", value.getCondition().toString());
        else if (site instanceof BreakStmt value) branch(owner, site, "break", value.getLabel().map(Node::toString).orElse("nearest_target"));
        else if (site instanceof ContinueStmt value) branch(owner, site, "continue", value.getLabel().map(Node::toString).orElse("nearest_loop"));
        else if (site instanceof BinaryExpr value && (value.getOperator() == BinaryExpr.Operator.AND || value.getOperator() == BinaryExpr.Operator.OR))
            branch(owner, site, "short_circuit", value.getLeft().toString());
        else if (site instanceof TryStmt value) {
            branch(owner, site, "try", "try");
            value.getFinallyBlock().ifPresent(block -> checklist.add(owner, block, "exception", "finally"));
            for (Expression resource : value.getResources()) checklist.add(owner, resource, "exception", "resource_cleanup")
                .property("rule", "java_try_with_resources_close_and_suppression");
        } else if (site instanceof CatchClause value) {
            branch(owner, site, "catch", value.getParameter().getType().toString());
            checklist.add(owner, site, "exception", "caught")
                .property("exception_type", value.getParameter().getType().toString())
                .property("handler_throw_syntax", value.getBody().findAll(ThrowStmt.class).isEmpty() ? "no_explicit_throw" : "contains_throw");
        } else if (site instanceof ThrowStmt value) {
            checklist.add(owner, site, "exception", "thrown").property("expression", value.getExpression().toString());
        } else if (site instanceof AssertStmt value) {
            branch(owner, site, "assert", value.getCheck().toString());
            checklist.add(owner, site, "exception", "assertion").property("condition", value.getCheck().toString());
        }
        if (site instanceof AssignExpr value) checklist.add(owner, site, "write", "assignment")
            .property("target", value.getTarget().toString()).property("value", value.getValue().toString())
            .property("operator", value.getOperator().asString()).property("observability", "not_classified");
        else if (site instanceof VariableDeclarator value && value.getInitializer().isPresent()) checklist.add(owner, site, "write", "variable_initializer")
            .property("target", value.getNameAsString()).property("value", value.getInitializer().orElseThrow().toString())
            .property("observability", "not_classified");
        else if (site instanceof UnaryExpr value && List.of(UnaryExpr.Operator.POSTFIX_DECREMENT, UnaryExpr.Operator.POSTFIX_INCREMENT,
                UnaryExpr.Operator.PREFIX_DECREMENT, UnaryExpr.Operator.PREFIX_INCREMENT).contains(value.getOperator()))
            checklist.add(owner, site, "write", "increment_decrement").property("target", value.getExpression().toString())
                .property("operator", value.getOperator().asString()).property("observability", "not_classified");
        else if (site instanceof ReturnStmt value) checklist.add(owner, site, "write", "return")
            .property("value", value.getExpression().map(Node::toString).orElse("void"));
        else if (site instanceof YieldStmt value) checklist.add(owner, site, "write", "yield").property("value", value.getExpression().toString());
        if (site instanceof UnaryExpr value && value.getExpression() instanceof LiteralExpr
                && (value.getOperator() == UnaryExpr.Operator.MINUS || value.getOperator() == UnaryExpr.Operator.PLUS))
            checklist.add(owner, site, "literal", "signed_number").property("value", value.toString());
        if (site instanceof FieldAccessExpr || site instanceof NameExpr) constant(site, owner);
        for (Node child : site.getChildNodes()) scan(child, owner);
    }

    private void branch(CodeNode owner, Node site, String detail, String condition) {
        checklist.add(owner, site, "branch", detail).property("condition", condition);
    }

    private void literal(LiteralExpr literal, CodeNode owner) {
        String value = literal.toString();
        if (literal instanceof StringLiteralExpr text) value = text.asString();
        else if (literal instanceof CharLiteralExpr text) value = String.valueOf(text.asChar());
        else if (literal instanceof TextBlockLiteralExpr text) value = text.asString();
        checklist.add(owner, literal, "literal", literal.getClass().getSimpleName()).property("value", value);
    }

    private void constant(Node site, CodeNode owner) {
        try {
            var resolved = site instanceof FieldAccessExpr value ? value.resolve() : ((NameExpr) site).resolve();
            if (resolved.isEnumConstant()) {
                var value = resolved.asEnumConstant();
                checklist.add(owner, site, "constant_reference", "enum_constant")
                    .property("target", value.getType().describe() + "." + value.getName())
                    .property("value_status", "symbolic");
                return;
            }
            if (!resolved.isField() || !resolved.asField().isStatic()) return;
            var field = resolved.asField();
            var type = checklist.graph.catalog.types.get(field.declaringType().getQualifiedName());
            String finality = "unknown";
            if (type != null) for (FieldDeclaration declaration : type.getFields()) {
                if (declaration.getVariables().stream().anyMatch(value -> value.getNameAsString().equals(field.getName())))
                    finality = declaration.isFinal() || type.isInterface() ? "final" : "mutable";
            }
            var item = checklist.add(owner, site, "constant_reference", "static_field")
                .property("target", field.declaringType().getQualifiedName() + "." + field.getName())
                .property("finality", finality).property("value_status", "not_evaluated");
            for (CodeNode node : checklist.graph.nodes.values()) {
                if (node.signature.equals(field.declaringType().getQualifiedName() + "." + field.getName())) item.candidates.add(node.id);
            }
        } catch (RuntimeException exception) {
            // The graph retains unresolved references; expose the uncertainty rather than omit the use.
            checklist.add(owner, site, "constant_reference", "unresolved_reference")
                .property("target", site.toString()).property("value_status", "unresolved");
        }
    }
}
