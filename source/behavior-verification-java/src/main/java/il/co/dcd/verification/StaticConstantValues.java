package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.BlockStmt;
import java.util.*;

/** Small side-effect-free evaluator. Unknown calls, mutable locals and field state stay unknown. */
final class StaticConstantValues {
    static final Object UNKNOWN = new Object();
    private final Node owner;
    private final String tagParameter, getter;
    private final Map<String, String> attributes;
    private Map<String, Object> fields = Map.of();

    StaticConstantValues(Node owner) { this(owner, null, null, Map.of()); }
    StaticConstantValues(Node owner, String tagParameter, String getter, Map<String, String> attributes) {
        this.owner = owner; this.tagParameter = tagParameter; this.getter = getter; this.attributes = attributes;
    }
    Object value(Expression expression) { return value(expression, new HashSet<>(), 0); }
    StaticConstantValues withFields(Map<String, Object> values) { fields = values; return this; }

    private Object value(Expression expression, Set<String> visiting, int depth) {
        if (depth > 32) return UNKNOWN;
        try {
            if (expression instanceof EnclosedExpr enclosed) return value(enclosed.getInner(), visiting, depth + 1);
            if (expression instanceof BooleanLiteralExpr literal) return literal.getValue();
            if (expression instanceof NullLiteralExpr) return null;
            if (expression instanceof StringLiteralExpr literal) return literal.asString();
            if (expression instanceof TextBlockLiteralExpr literal) return literal.asString();
            if (expression instanceof CharLiteralExpr literal) return literal.asChar();
            if (expression instanceof IntegerLiteralExpr literal) return literal.asNumber();
            if (expression instanceof LongLiteralExpr literal) return literal.asNumber();
            if (expression instanceof DoubleLiteralExpr literal) return literal.asDouble();
            if (expression instanceof NameExpr name) {
                Object local = local(name, visiting, depth);
                if (local != UNKNOWN) return local;
                try { return name.resolve().isField() ? fields.getOrDefault(name.getNameAsString(), UNKNOWN) : UNKNOWN; }
                catch (RuntimeException unresolved) { return UNKNOWN; }
            }
            if (expression instanceof FieldAccessExpr field && field.getScope().isThisExpr())
                return fields.getOrDefault(field.getNameAsString(), UNKNOWN);
            if (expression instanceof UnaryExpr unary) {
                Object operand = value(unary.getExpression(), visiting, depth + 1);
                if (unary.getOperator() == UnaryExpr.Operator.LOGICAL_COMPLEMENT && operand instanceof Boolean flag) return !flag;
                if (unary.getOperator() == UnaryExpr.Operator.MINUS && operand instanceof Number number) {
                    if (number instanceof Double) return -number.doubleValue();
                    if (number instanceof Long) return -number.longValue();
                    return -number.intValue();
                }
                if (unary.getOperator() == UnaryExpr.Operator.PLUS && operand instanceof Number) return operand;
                return UNKNOWN;
            }
            if (expression instanceof BinaryExpr binary) {
                Object left = value(binary.getLeft(), visiting, depth + 1);
                if (binary.getOperator() == BinaryExpr.Operator.AND && Boolean.FALSE.equals(left)) return false;
                if (binary.getOperator() == BinaryExpr.Operator.OR && Boolean.TRUE.equals(left)) return true;
                Object right = value(binary.getRight(), visiting, depth + 1);
                if (left == UNKNOWN || right == UNKNOWN) return UNKNOWN;
                return binary(binary, left, right);
            }
            if (expression instanceof ConditionalExpr conditional) {
                Object test = value(conditional.getCondition(), visiting, depth + 1);
                return test instanceof Boolean flag ? value(flag ? conditional.getThenExpr() : conditional.getElseExpr(), visiting, depth + 1) : UNKNOWN;
            }
            if (expression instanceof MethodCallExpr call && call.getScope().isPresent()) {
                if (tagParameter != null && call.getScope().get().isNameExpr()
                        && call.getScope().get().asNameExpr().getNameAsString().equals(tagParameter)
                        && call.getNameAsString().equals(getter) && call.getArguments().size() == 1
                        && call.getArgument(0) instanceof StringLiteralExpr key) return attributes.get(key.asString());
                Object receiver = value(call.getScope().get(), visiting, depth + 1);
                if (!(receiver instanceof String text)) return UNKNOWN;
                if (call.getArguments().isEmpty()) return switch (call.getNameAsString()) {
                    case "isEmpty" -> text.isEmpty(); case "isBlank" -> text.isBlank(); case "length" -> text.length(); default -> UNKNOWN;
                };
                if (call.getArguments().size() == 1) {
                    Object argument = value(call.getArgument(0), visiting, depth + 1);
                    if (argument == UNKNOWN) return UNKNOWN;
                    if (call.getNameAsString().equals("equals")) return text.equals(argument);
                    if (call.getNameAsString().equals("equalsIgnoreCase") && (argument == null || argument instanceof String)) return text.equalsIgnoreCase((String) argument);
                }
            }
        } catch (RuntimeException ignored) { return UNKNOWN; }
        return UNKNOWN;
    }

    private Object local(NameExpr name, Set<String> visiting, int depth) {
        String key = name.getNameAsString();
        if (owner == null || !visiting.add(key)) return UNKNOWN;
        try {
            var variables = owner.findAll(VariableDeclarator.class).stream().filter(variable -> variable.getNameAsString().equals(key)).toList();
            if (variables.size() != 1) return UNKNOWN;
            var variable = variables.get(0);
            if (variable.getInitializer().isEmpty() || variable.getBegin().orElseThrow().isAfter(name.getBegin().orElseThrow())) return UNKNOWN;
            if (variable.findAncestor(BlockStmt.class).filter(block -> block.isAncestorOf(name)).isEmpty()) return UNKNOWN;
            if (owner.findAll(AssignExpr.class).stream().anyMatch(assign -> assign.getTarget().isNameExpr() && assign.getTarget().asNameExpr().getNameAsString().equals(key))) return UNKNOWN;
            if (owner.findAll(UnaryExpr.class).stream().anyMatch(unary -> unary.getExpression().isNameExpr()
                    && unary.getExpression().asNameExpr().getNameAsString().equals(key) && Set.of(UnaryExpr.Operator.POSTFIX_INCREMENT,
                        UnaryExpr.Operator.POSTFIX_DECREMENT, UnaryExpr.Operator.PREFIX_INCREMENT, UnaryExpr.Operator.PREFIX_DECREMENT).contains(unary.getOperator()))) return UNKNOWN;
            var type = variable.getType();
            if (!type.isVarType() && !type.isPrimitiveType() && !type.resolve().describe().equals("java.lang.String")) return UNKNOWN;
            return value(variable.getInitializer().orElseThrow(), visiting, depth + 1);
        } finally { visiting.remove(key); }
    }

    private Object binary(BinaryExpr expression, Object left, Object right) {
        var operator = expression.getOperator();
        if (operator == BinaryExpr.Operator.AND && left instanceof Boolean a && right instanceof Boolean b) return a && b;
        if (operator == BinaryExpr.Operator.OR && left instanceof Boolean a && right instanceof Boolean b) return a || b;
        if (operator == BinaryExpr.Operator.PLUS && (left instanceof String || right instanceof String)) return String.valueOf(left) + right;
        if (Set.of(BinaryExpr.Operator.EQUALS, BinaryExpr.Operator.NOT_EQUALS).contains(operator)) {
            Boolean equal = null;
            if (left == null || right == null) equal = left == null && right == null;
            else if (left instanceof Boolean && right instanceof Boolean) equal = left.equals(right);
            else if (left instanceof Number a && right instanceof Number b) equal = numericEqual(a, b);
            // Do not equate runtime strings by value for Java reference-identity ==.
            if (equal != null) return operator == BinaryExpr.Operator.EQUALS ? equal : !equal;
        }
        if (left instanceof Number a && right instanceof Number b) {
            boolean floating = a instanceof Double || b instanceof Double;
            int compare = floating ? Double.compare(a.doubleValue(), b.doubleValue()) : Long.compare(a.longValue(), b.longValue());
            return switch (operator) {
                case LESS -> compare < 0; case LESS_EQUALS -> compare <= 0;
                case GREATER -> compare > 0; case GREATER_EQUALS -> compare >= 0; default -> UNKNOWN;
            };
        }
        return UNKNOWN;
    }
    private static boolean numericEqual(Number a, Number b) {
        return a instanceof Double || b instanceof Double ? a.doubleValue() == b.doubleValue() : a.longValue() == b.longValue();
    }
}
