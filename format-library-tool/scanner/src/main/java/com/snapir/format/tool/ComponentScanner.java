package com.snapir.format.tool;

import com.fasterxml.jackson.databind.*;
import com.github.javaparser.*;
import com.github.javaparser.ast.*;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.model.SymbolReference;
import com.github.javaparser.resolution.UnsolvedSymbolException;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.*;
import java.nio.file.*;
import java.util.*;
import java.util.jar.JarFile;

/** Read source/JAR types and dependencies; never load or execute application classes. */
public final class ComponentScanner {
    private final Map<String, Map<String, Object>> records = new TreeMap<>();
    private final Map<String, CombinedTypeSolver> solvers = new HashMap<>();
    private final Map<String, List<JavaParserTypeSolver>> projectSources = new HashMap<>();
    private final Map<String, CompilationUnit> units = new TreeMap<>();
    private final Map<String, String> owners = new HashMap<>();
    private final Map<String, String> declaredFiles = new HashMap<>();
    private final Set<String> frameworks = new HashSet<>();
    private final List<String> issues = new ArrayList<>();
    private final Map<String, Map<String, Map<String, Object>>> dependencyScopes = new TreeMap<>();
    private final JsonNode input;

    private ComponentScanner(JsonNode input) { this.input = input; }

    public static void main(String[] args) throws Exception {
        ObjectMapper json = new ObjectMapper();
        var scanner = new ComponentScanner(json.readTree(Path.of(args[0]).toFile()));
        scanner.scan();
        json.writerWithDefaultPrettyPrinter().writeValue(Path.of(args[1]).toFile(),
            Map.of("classes", scanner.records, "issues", scanner.issues, "dependency_scopes", scanner.dependencyScopes));
    }

    private static List<String> strings(JsonNode node) {
        List<String> result = new ArrayList<>();
        node.forEach(value -> result.add(value.asText()));
        return result;
    }

    private static void progress(String text) { System.out.println(text); System.out.flush(); }

    private void scan() throws Exception {
        for (String path : strings(input.path("framework_jars"))) {
            try (JarFile jar = new JarFile(path)) {
                jar.stream().filter(entry -> entry.getName().endsWith(".class")).forEach(entry ->
                    frameworks.add(entry.getName().replace('/', '.').replaceAll("\\.class$", "")));
            }
        }
        var parser = new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
        for (var source : input.path("sources")) {
            String file = source.path("file").asText();
            progress("Parsing " + file);
            var parsed = parser.parse(Files.readString(Path.of(file)).replaceFirst("^\\uFEFF", ""));
            if (!parsed.isSuccessful()) {
                issues.add("Invalid Java source " + file + ": " + parsed.getProblems());
                continue;
            }
            var unit = parsed.getResult().orElseThrow();
            units.put(file, unit);
            owners.put(file, source.path("project").asText());
            for (TypeDeclaration<?> declaration : unit.findAll(TypeDeclaration.class)) {
                if (declaration.findAncestor(CallableDeclaration.class).isPresent()) continue;
                declaration.getFullyQualifiedName().ifPresent(name -> {
                    String previous = declaredFiles.putIfAbsent(name, file);
                    if (previous != null && !previous.equals(file)) issues.add("Ambiguous source type: " + name);
                });
            }
        }
        for (var project : input.path("projects"))
            solvers.put(project.path("id").asText(),
                new CombinedTypeSolver(new ClassLoaderTypeSolver(ClassLoader.getPlatformClassLoader())));
        for (var project : input.path("projects")) {
            String identity = project.path("id").asText();
            var solver = solvers.get(identity);
            var config = new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE)
                .setSymbolResolver(new JavaSymbolSolver(solver));
            List<JavaParserTypeSolver> sourceRoots = new ArrayList<>();
            for (String root : strings(project.path("roots"))) {
                if (!Files.isDirectory(Path.of(root))) continue;
                var sourceSolver = new JavaParserTypeSolver(Path.of(root), config);
                sourceSolver.setParent(solver);
                sourceRoots.add(sourceSolver);
            }
            projectSources.put(identity, sourceRoots);
            solver.add(new OwnedSources(new HashSet<>(strings(project.path("visible_projects")))));
            for (String library : strings(project.path("libraries"))) {
                if (Files.isRegularFile(Path.of(library))) {
                    progress("Indexing dependency " + library);
                    solver.add(new JarTypeSolver(library));
                }
            }
        }
        Map<String, TypeDeclaration<?>> declarations = new TreeMap<>();
        for (var item : units.entrySet()) {
            String file = item.getKey();
            var solver = solvers.get(owners.get(file));
            new JavaSymbolSolver(solver).inject(item.getValue());
            for (TypeDeclaration<?> declaration : item.getValue().findAll(TypeDeclaration.class)) {
                if (declaration.findAncestor(CallableDeclaration.class).isPresent()) continue;
                String name = declaration.getFullyQualifiedName().orElse("");
                progress("Resolving " + name);
                Map<String, Object> record = new LinkedHashMap<>();
                record.put("name", name); record.put("file", file); record.put("project", owners.get(file));
                record.put("abstract", !(declaration instanceof ClassOrInterfaceDeclaration concrete)
                    || concrete.isAbstract() || concrete.isInterface());
                record.put("framework", frameworks.contains(name));
                List<String> problems = new ArrayList<>();
                Set<String> missing = new TreeSet<>();
                Set<String> dependencies = new TreeSet<>();
                List<String> ancestors = new ArrayList<>();
                List<Map<String, String>> relations = new ArrayList<>();
                String kind = "support";
                try {
                    if (declaration instanceof ClassOrInterfaceDeclaration original) {
                        collectAncestors(original.resolve(), new HashSet<>(), ancestors);
                        for (var parent : original.getExtendedTypes())
                            relations.add(Map.of("kind", "extends", "target", parent.resolve().asReferenceType().getQualifiedName()));
                        for (var parent : original.getImplementedTypes())
                            relations.add(Map.of("kind", "implements", "target", parent.resolve().asReferenceType().getQualifiedName()));
                    }
                    if (ancestors.contains(input.path("format_base_class").asText())
                            || name.equals(input.path("format_base_class").asText())) kind = "format";
                    for (String base : strings(input.path("decorator_base_classes")))
                        if (ancestors.contains(base) || name.equals(base)) kind = "decorator";
                    record.put("ancestry_status", "resolved");
                } catch (RuntimeException error) {
                    record.put("ancestry_status", "unresolved");
                    unresolved(problems, missing, "Ancestry", name, error, item.getValue());
                }
                dependencies.addAll(ancestors);
                record.put("kind", kind);
                record.put("ancestors", ancestors);
                record.put("relations", relations);
                record.put("binary_ancestors", ancestors.stream().filter(value -> !declaredFiles.containsKey(value)).toList());
                record.put("declaration_kind", declaration instanceof ClassOrInterfaceDeclaration original
                    ? (original.isInterface() ? "interface" : "class") : "support");
                record.put("dependencies", dependencies);
                record.put("issues", problems);
                record.put("unresolved_dependencies", missing);
                record.put("dependency_status", "ignored");
                records.put(name, record);
                declarations.put(name, declaration);
            }
        }
        // Keep each target's reached members isolated from other targets using the same helpers.
        Set<String> foundations = new TreeSet<>(strings(input.path("foundation_classes")));
        Set<String> roots = new TreeSet<>(foundations);
        for (var item : records.entrySet())
            if (!item.getValue().get("kind").equals("support")) roots.add(item.getKey());
        for (String root : roots) {
            if (!records.containsKey(root)) continue;
            progress("Inspecting required members " + root);
            dependencyScopes.put(root, new RequiredDependencies(records, declarations, solvers)
                .analyze(root, foundations.contains(root)));
        }
        // Flat records remain an inventory/log view; planning consumes the per-target scopes.
        for (var scope : dependencyScopes.values())
            for (var item : scope.entrySet()) {
                var target = records.get(item.getKey());
                target.put("dependency_status", "analyzed");
                for (String key : List.of("dependencies", "issues", "unresolved_dependencies"))
                    for (Object value : (Collection<?>) item.getValue().get(key))
                        if (!((Collection<?>) target.get(key)).contains(value)) ((Collection) target.get(key)).add(value);
            }
    }

    private void unresolved(List<String> problems, Set<String> missing, String kind, String subject,
                            RuntimeException error, CompilationUnit unit) {
        problems.add(kind + " unresolved: " + subject + ": " + error.getMessage());
        String symbol = null;
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            if (cause instanceof UnsolvedSymbolException unresolved) {
                symbol = unresolved.getName();
                break;
            }
        }
        if (symbol == null || symbol.isBlank()) {
            missing.add(kind + " dependency: " + subject);
            return;
        }
        // An explicit import supplies a qualified class identity; never guess wildcard imports.
        String simple = symbol.replaceAll("<.*>", "").split("\\.")[0];
        for (var imported : unit.getImports()) {
            if (!imported.isAsterisk() && !imported.isStatic()
                    && imported.getName().getIdentifier().equals(simple)) {
                missing.add(imported.getNameAsString());
                return;
            }
        }
        missing.add(symbol);
    }

    /** Resolve each source in its owner's dependency context, not a consumer's JAR list. */
    private final class OwnedSources implements TypeSolver {
        private final Set<String> visible;
        private TypeSolver parent;
        OwnedSources(Set<String> visible) { this.visible = visible; }
        public TypeSolver getParent() { return parent; }
        public void setParent(TypeSolver value) { parent = value; }
        public SymbolReference<ResolvedReferenceTypeDeclaration> tryToSolveTypeInModule(String name, String moduleName) {
            return tryToSolveType(name);
        }
        public SymbolReference<ResolvedReferenceTypeDeclaration> tryToSolveType(String name) {
            String file = declaredFiles.get(name);
            String owner = owners.get(file);
            if (owner == null || !visible.contains(owner)) return SymbolReference.unsolved();
            for (var source : projectSources.getOrDefault(owner, List.of())) {
                var result = source.tryToSolveType(name);
                if (result.isSolved()) return result;
            }
            return SymbolReference.unsolved();
        }
    }

    private void collectAncestors(ResolvedReferenceTypeDeclaration declaration, Set<String> seen, List<String> result) {
        if (!seen.add(declaration.getQualifiedName())) return;
        for (var ancestor : declaration.getAncestors()) {
            String name = ancestor.getQualifiedName();
            if (!result.contains(name)) result.add(name);
            ancestor.getTypeDeclaration().ifPresent(parent -> collectAncestors(parent, seen, result));
        }
    }
}
