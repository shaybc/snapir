package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.*;
import il.co.dcd.verification.harness.BoundaryValues;
import java.util.*;
import org.w3c.dom.Element;

/** Parse current native files; comments/tests/imports cannot supply implementation evidence. */
final class NativeInspection {
    private NativeInspection() { }

    static Map<String, Object> inspect(Element input) {
        Map<String, Object> files = new LinkedHashMap<>(), queries = new LinkedHashMap<>();
        JavaParser parser = new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE).setTabSize(1));
        for (Element file : BoundaryValues.children(input, "file")) {
            String path = file.getAttribute("path"), content = BoundaryValues.child(file, "source").getTextContent();
            var parsed = parser.parse(content);
            if (!parsed.isSuccessful()) throw new IllegalArgumentException("Candidate Java parse failed: " + path + ": " + parsed.getProblems());
            var unit = parsed.getResult().orElseThrow();
            String pkg = unit.getPackageDeclaration().map(value -> value.getNameAsString()).orElse("");
            if (unit.getTypes().isEmpty()) throw new IllegalArgumentException("Candidate file has no type: " + path);
            var main = unit.getTypes().stream().filter(value -> value.isPublic()).findFirst().orElse(unit.getType(0));
            String expected = "src/main/java/" + (pkg.isEmpty() ? "" : pkg.replace('.', '/') + "/") + main.getNameAsString() + ".java";
            if (!path.equals(expected)) throw new IllegalArgumentException("Candidate filename/package mismatch: " + path);
            boolean[] code = new boolean[content.length()];
            for (var token : unit.getTokenRange().orElseThrow()) {
                if (token.getCategory().isWhitespaceOrComment() || token.getRange().isEmpty()) continue;
                var range = token.getRange().orElseThrow();
                if (unit.getImports().stream().anyMatch(value -> value.getRange().orElseThrow().contains(range))
                    || unit.getPackageDeclaration().filter(value -> value.getRange().orElseThrow().contains(range)).isPresent()) continue;
                int begin = offset(content, range.begin.line, range.begin.column), end = offset(content, range.end.line, range.end.column) + 1;
                Arrays.fill(code, begin, Math.min(end, code.length), true);
            }
            List<Map<String, Object>> literals = new ArrayList<>();
            var constants = new StaticConstantValues(null);
            for (LiteralExpr literal : unit.findAll(LiteralExpr.class)) {
                Object value = constants.value(literal);
                literals.add(Map.of("category", category(literal), "value", value == null ? "null" : String.valueOf(value)));
                if (!(literal instanceof StringLiteralExpr || literal instanceof TextBlockLiteralExpr || literal instanceof CharLiteralExpr))
                    literals.add(Map.of("category", category(literal), "value", literal.toString()));
            }
            for (Expression expression : unit.findAll(Expression.class)) {
                if (!(expression instanceof BinaryExpr || expression instanceof UnaryExpr || expression instanceof ConditionalExpr)) continue;
                Object value = constants.value(expression);
                if (value != StaticConstantValues.UNKNOWN && value != null)
                    literals.add(Map.of("category", value instanceof String ? "string" : value instanceof Boolean ? "boolean" : value instanceof Character ? "character" : "number", "value", String.valueOf(value)));
            }
            files.put(path, Map.of("literals", literals));
            for (Element query : BoundaryValues.children(file, "location")) {
                String excerpt = (String) BoundaryValues.read(BoundaryValues.child(query, "excerpt"));
                boolean found = false;
                for (int at = content.indexOf(excerpt); at >= 0 && !excerpt.isBlank(); at = content.indexOf(excerpt, at + 1)) {
                    for (int index = at; index < at + excerpt.length(); index++) if (code[index]) { found = true; break; }
                    if (found) break;
                }
                queries.put(query.getAttribute("id"), found);
            }
        }
        return Map.of("files", files, "locations", queries);
    }
    private static String category(LiteralExpr literal) {
        if (literal instanceof StringLiteralExpr || literal instanceof TextBlockLiteralExpr) return "string";
        if (literal instanceof CharLiteralExpr) return "character";
        if (literal instanceof BooleanLiteralExpr) return "boolean";
        if (literal instanceof NullLiteralExpr) return "null";
        return "number";
    }
    private static int offset(String text, int line, int column) {
        int at = 0, current = 1;
        while (current < line && at < text.length()) if (text.charAt(at++) == '\n') current++;
        return at + column - 1;
    }
}
