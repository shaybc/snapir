package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ClassLoaderTypeSolver;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import javax.lang.model.SourceVersion;
import org.w3c.dom.Element;

/** Isolated, disposable source root containing only one unit's supplied Java evidence. */
final class SourceScope implements AutoCloseable {
    private final Path root;
    private final Map<Path, Element> evidence = new HashMap<>();
    final Set<String> typeNames = new TreeSet<>();
    final CombinedTypeSolver solver;

    SourceScope(Element scope) throws IOException {
        root = Files.createTempDirectory("snapir-unit-source-");
        try {
            ParserConfiguration configuration = new ParserConfiguration()
                .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE)
                .setCharacterEncoding(StandardCharsets.UTF_8);
            JavaParser parser = new JavaParser(configuration);
            for (org.w3c.dom.Node node = scope.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (!(node instanceof Element source) || !source.getTagName().equals("source")) continue;
                var parsed = parser.parse(source.getTextContent());
                if (!parsed.isSuccessful()) throw new IllegalArgumentException("Invalid Java source " + source.getAttribute("identity") + ": " + parsed.getProblems());
                CompilationUnit unit = parsed.getResult().orElseThrow();
                for (ClassOrInterfaceDeclaration type : unit.findAll(ClassOrInterfaceDeclaration.class)) {
                    if (type.findAncestor(CallableDeclaration.class).isEmpty()) type.getFullyQualifiedName().ifPresent(typeNames::add);
                }
                if (unit.getTypes().isEmpty()) continue;
                String packageName = unit.getPackageDeclaration().map(value -> value.getNameAsString()).orElse("");
                String filename = unit.getTypes().stream().filter(value -> value.isPublic()).findFirst()
                    .orElse(unit.getType(0)).getNameAsString();
                if ((!packageName.isEmpty() && !SourceVersion.isName(packageName)) || !SourceVersion.isIdentifier(filename)) {
                    throw new IllegalArgumentException("Invalid Java source package or type name");
                }
                Path path = root.resolve(packageName.replace('.', '/')).resolve(filename + ".java").normalize();
                if (!path.startsWith(root) || evidence.putIfAbsent(path, source) != null) {
                    throw new IllegalArgumentException("Conflicting Java evidence for " + packageName + "." + filename);
                }
                Files.createDirectories(path.getParent());
                Files.writeString(path, source.getTextContent(), StandardCharsets.UTF_8);
            }
            // The platform loader sees JDK modules (including DOM/SAX), never tool or workspace classes.
            solver = new CombinedTypeSolver(new ClassLoaderTypeSolver(ClassLoader.getPlatformClassLoader()), new JavaParserTypeSolver(root, configuration));
        } catch (IOException | RuntimeException exception) {
            close();
            throw exception;
        }
    }

    void bind(Node node) {
        node.findCompilationUnit().ifPresent(unit -> new JavaSymbolSolver(solver).inject(unit));
    }

    Element evidence(CompilationUnit unit) {
        Path path = unit.getStorage().orElseThrow(() -> new IllegalStateException("Method has no original source storage")).getPath();
        Element source = evidence.get(path.toAbsolutePath().normalize());
        if (source == null) throw new IllegalStateException("Method resolved outside the supplied unit evidence");
        return source;
    }

    @Override
    public void close() throws IOException {
        try (var paths = Files.walk(root)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path);
        }
    }
}
