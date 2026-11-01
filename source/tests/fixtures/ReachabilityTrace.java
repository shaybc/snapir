package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.ast.stmt.ExpressionStmt;
import com.github.javaparser.StaticJavaParser;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;

/** Test-only probes in disposable copies of original source; never production instrumentation. */
public class ReachabilityTrace {
    public static void main(String[] args) throws Exception {
        Element manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(Path.of(args[0]).toFile()).getDocumentElement();
        try (SourceScope sources = new SourceScope(manifest)) {
            JavaParser parser = new JavaParser(new ParserConfiguration()
                .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
            for (var child = manifest.getFirstChild(); child != null; child = child.getNextSibling()) {
                if (!(child instanceof Element source)) continue;
                var unit = parser.parse(source.getTextContent()).getResult().orElseThrow();
                sources.bind(unit);
                for (MethodDeclaration method : unit.findAll(MethodDeclaration.class)) {
                    if (method.getBody().isEmpty()) continue;
                    String signature = method.resolve().getQualifiedSignature();
                    var call = new MethodCallExpr(StaticJavaParser.parseExpression("System.out"), "println")
                        .addArgument(new StringLiteralExpr("TRACE:" + signature));
                    method.getBody().orElseThrow().addStatement(0, new ExpressionStmt(call));
                }
                String pkg = unit.getPackageDeclaration().orElseThrow().getNameAsString();
                Path file = Path.of(args[1]).resolve(pkg.replace('.', '/'))
                    .resolve(unit.getType(0).getNameAsString() + ".java");
                Files.createDirectories(file.getParent());
                Files.writeString(file, unit.toString());
            }
        }
    }
}
