package il.co.dcd.verification;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import org.w3c.dom.Element;

/** Source-range probes preserve conditions and evaluate each original expression once. */
final class HarnessProbes {
    static final String RUNTIME = "il.co.dcd.verification.harness.BoundaryRuntime";
    private HarnessProbes() { }

    static MethodCallExpr call(String name, Expression... arguments) {
        MethodCallExpr call = new MethodCallExpr(StaticJavaParser.parseExpression(RUNTIME), name);
        for (Expression argument : arguments) call.addArgument(argument);
        return call;
    }
    static Statement hit(String id, String outcome) { return new ExpressionStmt(call("hit", new StringLiteralExpr(id), new StringLiteralExpr(outcome))); }

    static void method(Node node, String identity) {
        if (node instanceof MethodDeclaration method && method.getBody().isPresent()) method.getBody().orElseThrow().addStatement(0, hit(identity, "entered"));
        else if (node instanceof ConstructorDeclaration constructor) {
            int at = !constructor.getBody().getStatements().isEmpty() && constructor.getBody().getStatement(0) instanceof ExplicitConstructorInvocationStmt ? 1 : 0;
            constructor.getBody().addStatement(at, hit(identity, "entered"));
        } else if (node instanceof InitializerDeclaration initializer) initializer.getBody().addStatement(0, hit(identity, "entered"));
    }

    static void branch(Node node, Element item) {
        String id = item.getAttribute("id"), detail = item.getAttribute("detail");
        if (node instanceof IfStmt statement) statement.setCondition(condition(id, statement.getCondition()));
        else if (node instanceof ConditionalExpr expression) expression.setCondition(condition(id, expression.getCondition()));
        else if (node instanceof WhileStmt statement) statement.setCondition(condition(id, statement.getCondition()));
        else if (node instanceof DoStmt statement) statement.setCondition(condition(id, statement.getCondition()));
        else if (node instanceof ForStmt statement) statement.setCompare(condition(id, statement.getCompare().orElse(new BooleanLiteralExpr(true))));
        else if (node instanceof ForEachStmt statement) statement.setIterable(call("iteration", new StringLiteralExpr(id), statement.getIterable().clone()));
        else if (node instanceof BinaryExpr expression) expression.setLeft(condition(id, expression.getLeft()));
        else if (node instanceof SwitchStmt statement) statement.setSelector(value(id, statement.getSelector()));
        else if (node instanceof SwitchExpr expression) expression.setSelector(value(id, expression.getSelector()));
        else if (node instanceof CatchClause clause) clause.getBody().addStatement(0, hit(id, "entered"));
        else if (node instanceof TryStmt statement) statement.getTryBlock().addStatement(0, hit(id, "entered"));
        else if (node instanceof SwitchEntry entry) {
            if (entry.getType() == SwitchEntry.Type.EXPRESSION) {
                Expression expression = entry.getStatement(0).asExpressionStmt().getExpression().clone();
                BlockStmt block = new BlockStmt().addStatement(hit(id, "entered"));
                if (entry.getParentNode().orElseThrow() instanceof SwitchExpr) block.addStatement(new YieldStmt(expression));
                else block.addStatement(new ExpressionStmt(expression));
                entry.setType(SwitchEntry.Type.BLOCK); entry.setStatements(new com.github.javaparser.ast.NodeList<>(block));
            } else if (entry.getType() == SwitchEntry.Type.BLOCK) entry.getStatement(0).asBlockStmt().addStatement(0, hit(id, "entered"));
            else if (entry.getType() != SwitchEntry.Type.STATEMENT_GROUP) {
                BlockStmt block = new BlockStmt().addStatement(hit(id, "entered"));
                for (Statement statement : entry.getStatements()) block.addStatement(statement.clone());
                entry.setType(SwitchEntry.Type.BLOCK); entry.setStatements(new com.github.javaparser.ast.NodeList<>(block));
            } else entry.getStatements().add(0, hit(id, "entered"));
        } else if (node instanceof AssertStmt statement) statement.setCheck(condition(id, statement.getCheck()));
        else if (detail.equals("switch_guard") && node instanceof Expression expression) expression.replace(condition(id, expression.clone()));
        else if (node instanceof BreakStmt || node instanceof ContinueStmt) {
            node.replace(new BlockStmt().addStatement(hit(id, "entered")).addStatement((Statement) node.clone()));
        }
    }
    private static Expression condition(String id, Expression original) { return call("condition", new StringLiteralExpr(id), original.clone()); }
    private static Expression value(String id, Expression original) { return call("value", new StringLiteralExpr(id), original.clone()); }
}
