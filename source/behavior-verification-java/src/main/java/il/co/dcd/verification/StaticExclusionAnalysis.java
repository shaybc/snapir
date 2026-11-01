package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Prove lexical dead branches only; unknown state and call targets never become exclusions. */
final class StaticExclusionAnalysis {
    private StaticExclusionAnalysis() { }

    static Map<String, Object> inspect(Element input) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        try (SourceScope scope = new SourceScope(input)) {
            SourceCatalog catalog = new SourceCatalog(scope);
            if (!catalog.problems.isEmpty()) throw new IllegalArgumentException(catalog.problems.toString());
            for (Element item : BoundaryValues.children(input, "item")) {
                CodeNode owner = catalog.nodes.get(item.getAttribute("code_node_id"));
                if (owner == null || !owner.source.getAttribute("identity").equals(item.getAttribute("source_identity"))
                    || !owner.source.getAttribute("hash").equals(item.getAttribute("source_hash")))
                    throw new IllegalArgumentException("Checklist source owner changed: " + item.getAttribute("id"));
                Node site = owner.anchor.findAll(Node.class).stream().filter(node -> matches(node, item)).findFirst().orElse(null);
                // Synthetic markers have no AST node; plumbing validation handles these separately.
                if (site != null) {
                    Map<String, Object> proof = deadBranch(site, ConfiguredGuardValues.evaluators(owner, catalog, input));
                    if (!proof.isEmpty()) result.put(item.getAttribute("id"), proof);
                }
            }
            StaticReachabilityExclusions.inspect(input, catalog).forEach(result::putIfAbsent);
        }
        return result;
    }

    private static boolean matches(Node node, Element item) {
        if (!node.getClass().getSimpleName().equals(item.getAttribute("syntax_type")) || node.getRange().isEmpty()) return false;
        var r = node.getRange().orElseThrow();
        return r.begin.line == Integer.parseInt(item.getAttribute("start_line"))
            && r.begin.column == Integer.parseInt(item.getAttribute("start_column"))
            && r.end.line == Integer.parseInt(item.getAttribute("end_line"))
            && r.end.column == Integer.parseInt(item.getAttribute("end_column"));
    }

    static Map<String, Object> deadBranch(Node site, List<StaticConstantValues> configured) {
        for (Node parent : ancestors(site)) {
            if (parent instanceof CallableDeclaration<?> || parent instanceof TypeDeclaration<?> || parent instanceof LambdaExpr) break;
            Expression condition = null;
            Node skipped = null;
            if (parent instanceof IfStmt branch) {
                condition = branch.getCondition();
                Object flag = guard(condition, configured);
                if (Boolean.FALSE.equals(flag)) skipped = branch.getThenStmt();
                if (Boolean.TRUE.equals(flag)) skipped = branch.getElseStmt().orElse(null);
            } else if (parent instanceof ConditionalExpr branch) {
                condition = branch.getCondition();
                Object flag = guard(condition, configured);
                if (flag instanceof Boolean value) skipped = value ? branch.getElseExpr() : branch.getThenExpr();
            } else if (parent instanceof WhileStmt loop) {
                condition = loop.getCondition();
                if (Boolean.FALSE.equals(guard(condition, configured))) skipped = loop.getBody();
            } else if (parent instanceof BinaryExpr binary) {
                condition = binary.getLeft();
                if (binary.getOperator() == BinaryExpr.Operator.AND && Boolean.FALSE.equals(guard(condition, configured))
                    || binary.getOperator() == BinaryExpr.Operator.OR && Boolean.TRUE.equals(guard(condition, configured))) skipped = binary.getRight();
            }
            if (skipped != null && (skipped == site || skipped.isAncestorOf(site)))
                return Map.of("reason", "branch_fixed_off", "rule_id", pureBoolean(condition) instanceof Boolean ? "literal_boolean_guard" : "configured_readonly_tag_guard",
                    "predicate", condition.toString(), "predicate_value", guard(condition, configured).toString(),
                    "origin", pureBoolean(condition) instanceof Boolean ? "source_constant" : "pinned_tag_contract_all_occurrences");
        }
        return Map.of();
    }

    private static Object guard(Expression expression, List<StaticConstantValues> configured) {
        Object literal = pureBoolean(expression);
        if (literal instanceof Boolean || configured.isEmpty()) return literal;
        // No local/field guesses or numeric coercion. Only Tag reads and known String operations.
        if (!expression.findAll(FieldAccessExpr.class).isEmpty() || !expression.findAll(AssignExpr.class).isEmpty()
            || !expression.findAll(CastExpr.class).isEmpty() || !expression.findAll(ObjectCreationExpr.class).isEmpty()
            || !expression.findAll(IntegerLiteralExpr.class).isEmpty() || !expression.findAll(DoubleLiteralExpr.class).isEmpty()
            || !expression.findAll(LongLiteralExpr.class).isEmpty()) return StaticConstantValues.UNKNOWN;
        Object expected = configured.get(0).value(expression);
        if (!(expected instanceof Boolean)) return StaticConstantValues.UNKNOWN;
        return configured.stream().allMatch(values -> expected.equals(values.value(expression))) ? expected : StaticConstantValues.UNKNOWN;
    }

    private static List<Node> ancestors(Node site) {
        List<Node> result = new ArrayList<>();
        for (Node parent = site.getParentNode().orElse(null); parent != null; parent = parent.getParentNode().orElse(null)) result.add(parent);
        return result;
    }

    private static Object pureBoolean(Expression expression) {
        // Deliberately narrow: no mutable locals, casts, runtime settings, calls or numeric promotion guesses.
        if (expression instanceof BooleanLiteralExpr literal) return literal.getValue();
        if (expression instanceof EnclosedExpr enclosed) return pureBoolean(enclosed.getInner());
        if (expression instanceof UnaryExpr unary && unary.getOperator() == UnaryExpr.Operator.LOGICAL_COMPLEMENT) {
            Object value = pureBoolean(unary.getExpression());
            return value instanceof Boolean flag ? !flag : StaticConstantValues.UNKNOWN;
        }
        if (expression instanceof BinaryExpr binary) {
            Object left = pureBoolean(binary.getLeft());
            if (binary.getOperator() == BinaryExpr.Operator.AND && Boolean.FALSE.equals(left)) return false;
            if (binary.getOperator() == BinaryExpr.Operator.OR && Boolean.TRUE.equals(left)) return true;
            Object right = pureBoolean(binary.getRight());
            if (left instanceof Boolean a && right instanceof Boolean b) return switch (binary.getOperator()) {
                case AND -> a && b; case OR -> a || b; case EQUALS -> a == b; case NOT_EQUALS -> a != b;
                default -> StaticConstantValues.UNKNOWN;
            };
        }
        return StaticConstantValues.UNKNOWN;
    }
}
