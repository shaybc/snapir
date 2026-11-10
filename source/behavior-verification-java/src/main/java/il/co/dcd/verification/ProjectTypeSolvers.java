package il.co.dcd.verification;

import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import com.github.javaparser.resolution.model.SymbolReference;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.*;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.*;
import org.w3c.dom.Element;

/** Keep each supplied source's symbol resolution in its verified owning project. */
final class ProjectTypeSolvers {
    private final Map<String, CombinedTypeSolver> projects = new HashMap<>();
    private final Map<String, JavaParserTypeSolver> sources = new HashMap<>();
    private final Map<String, String> owners;

    ProjectTypeSolvers(Element scope, Map<String, Path> roots, Map<String, String> owners,
                       Map<String, String> identities) throws IOException {
        this.owners = owners;
        for (var node = scope.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (!(node instanceof Element project) || !project.getTagName().equals("project")) continue;
            String name = project.getAttribute("id");
            var solver = new CombinedTypeSolver(new ClassLoaderTypeSolver(ClassLoader.getPlatformClassLoader()));
            if (projects.putIfAbsent(name, solver) != null || !roots.containsKey(name))
                throw new IllegalArgumentException("Missing or duplicate source project: " + name);
            ParserConfiguration configuration = new ParserConfiguration()
                .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE)
                .setSymbolResolver(new JavaSymbolSolver(solver));
            var sourceSolver = new JavaParserTypeSolver(roots.get(name), configuration);
            sourceSolver.setParent(solver);
            sources.put(name, sourceSolver);
            Set<String> visible = new HashSet<>();
            for (var child = project.getFirstChild(); child != null; child = child.getNextSibling())
                if (child instanceof Element element && element.getTagName().equals("visible-source"))
                    visible.add(element.getAttribute("identity"));
            solver.add(new OwnedSources(visible, identities));
            for (var child = project.getFirstChild(); child != null; child = child.getNextSibling()) {
                if (!(child instanceof Element library) || !library.getTagName().equals("library")) continue;
                Path path = Path.of(library.getAttribute("path"));
                AnalysisProgress.report("project " + name + " verifying JAR " + path.getFileName());
                if (!path.isAbsolute() || !Files.isRegularFile(path) || !Files.isReadable(path))
                    throw new IllegalArgumentException("Invalid JAR path for project " + name + ": " + path);
                try {
                    var digest = MessageDigest.getInstance("SHA-256");
                    try (var input = new DigestInputStream(Files.newInputStream(path), digest)) {
                        input.transferTo(java.io.OutputStream.nullOutputStream());
                    }
                    if (!HexFormat.of().formatHex(digest.digest()).equals(library.getAttribute("sha256")))
                        throw new IllegalArgumentException("JAR changed for project " + name + ": " + path);
                } catch (java.security.NoSuchAlgorithmException impossible) {
                    throw new IllegalStateException(impossible);
                }
                // CombinedTypeSolver retains this order; JAR contents are inspected, never executed.
                AnalysisProgress.report("project " + name + " loading JAR " + path.getFileName());
                solver.add(new JarTypeSolver(path));
                AnalysisProgress.report("project " + name + " loaded JAR " + path.getFileName());
            }
        }
    }

    CombinedTypeSolver forProject(String project) {
        var result = projects.get(project);
        if (result == null) throw new IllegalArgumentException("Unknown boundary source project: " + project);
        return result;
    }

    CombinedTypeSolver forType(String type) { return forProject(owners.get(type)); }

    /** Route visible source declarations to their owner's parser and dependency context. */
    private final class OwnedSources implements TypeSolver {
        private final Set<String> visible;
        private final Map<String, String> identities;
        private TypeSolver parent;
        OwnedSources(Set<String> visible, Map<String, String> identities) {
            this.visible = visible; this.identities = identities;
        }
        public TypeSolver getParent() { return parent; }
        public void setParent(TypeSolver parent) { this.parent = parent; }
        public SymbolReference<ResolvedReferenceTypeDeclaration> tryToSolveType(String name) {
            String owner = owners.get(name);
            return owner != null && visible.contains(identities.get(name))
                ? sources.get(owner).tryToSolveType(name) : SymbolReference.unsolved();
        }
        public SymbolReference<ResolvedReferenceTypeDeclaration> tryToSolveTypeInModule(String name, String module) {
            return tryToSolveType(name);
        }
    }
}
