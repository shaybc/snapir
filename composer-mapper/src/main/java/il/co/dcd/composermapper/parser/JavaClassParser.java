package il.co.dcd.composermapper.parser;

import il.co.dcd.composermapper.model.JavaClassDef;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.*;

public class JavaClassParser {

    private static final Pattern PACKAGE_PATTERN =
        Pattern.compile("(?m)^\\s*package\\s+([a-zA-Z0-9_.]+)\\s*;");
    private static final Pattern IMPORT_PATTERN =
        Pattern.compile("(?m)^\\s*import\\s+([a-zA-Z0-9_.*]+)\\s*;");
    private static final Pattern CLASS_PATTERN =
        Pattern.compile("(?m)^\\s*(?:public\\s+)?(?:abstract\\s+|final\\s+)?(?:class|interface|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)\\b");
    private static final Pattern EXTENDS_PATTERN =
        Pattern.compile("(?m)(?:class|interface)\\s+\\w[\\w<>, ]*\\s+extends\\s+([A-Za-z_][A-Za-z0-9_.<>, ]*)(?:\\s+implements|\\s*\\{)");
    private static final Pattern IMPLEMENTS_PATTERN =
        Pattern.compile("(?m)class\\s+\\w[\\w<>, ]*(?:\\s+extends\\s+[^{]+)?\\s+implements\\s+([A-Za-z_][A-Za-z0-9_.<>, ]*)\\s*\\{");
    private static final Pattern METHOD_PATTERN =
        Pattern.compile("(?m)^\\s*(?:public|protected|private)?\\s*(?:static\\s+)?(?:final\\s+)?(?:synchronized\\s+)?(?:[A-Za-z_][A-Za-z0-9_<>\\[\\], ?]+)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^)]*)\\)\\s*(?:throws\\s+([^\\{]+))?\\{");
    private static final Pattern INT_CONSTANT_PATTERN =
        Pattern.compile("(?m)^\\s*(?:public|protected|private)?\\s*static\\s+final\\s+int\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(-?\\d+)\\s*;");
    private static final Pattern RETURN_PATTERN =
        Pattern.compile("\\breturn\\s+(-?\\d+|[A-Za-z_][A-Za-z0-9_]*)\\s*;");
    private static final Pattern THROW_NEW_PATTERN =
        Pattern.compile("\\bthrow\\s+new\\s+([A-Za-z_][A-Za-z0-9_.$]*)\\s*\\(");
    private static final Pattern JAVADOC_PATTERN =
        Pattern.compile("(?s)/\\*\\*(.*?)\\*/");
    private static final Pattern JAVADOC_RETURN_CODE_PATTERN =
        Pattern.compile("(?i)(?:returns?\\s*)?(-?\\d+)\\s*(?:\\(([^)]+)\\)|[-:=]\\s*([^,;\\n\\r.]+))");

    public JavaClassDef parse(Path javaFile) {
        try {
            String content = Files.readString(javaFile, StandardCharsets.UTF_8);
            String packageName = matchFirst(PACKAGE_PATTERN, content);
            String simpleName  = matchFirst(CLASS_PATTERN, content);
            if (simpleName == null || simpleName.isBlank()) return null;

            JavaClassDef def = new JavaClassDef();
            def.setSourceFile(javaFile);
            def.setPackageName(packageName == null ? "" : packageName);
            def.setSimpleName(simpleName);
            def.setFullyQualifiedName(
                packageName == null || packageName.isBlank() ? simpleName : packageName + "." + simpleName);

            // Build import map: simpleName -> FQCN for resolution
            Map<String, String> importMap = new LinkedHashMap<>();
            Matcher im = IMPORT_PATTERN.matcher(content);
            while (im.find()) {
                String fqcn = im.group(1).trim();
                def.getImports().add(fqcn);
                if (fqcn.contains(".")) {
                    String sn = fqcn.substring(fqcn.lastIndexOf('.') + 1);
                    importMap.put(sn, fqcn);
                }
                if (fqcn.startsWith("com.ibm") || fqcn.startsWith("com.ibm."))
                    def.getInferredExternalDependencies().add("IBM/WAS");
                if (fqcn.contains("java.sql") || fqcn.contains("javax.sql")
                        || fqcn.contains("JdbcTemplate") || fqcn.contains("DataSource"))
                    def.getInferredExternalDependencies().add("Database");
                if (fqcn.contains("HttpClient") || fqcn.contains("RestTemplate")
                        || fqcn.contains("WebClient") || fqcn.contains("HttpURLConnection"))
                    def.getInferredExternalDependencies().add("API/Service");
            }

            // extends
            String rawExtends = matchFirst(EXTENDS_PATTERN, content);
            if (rawExtends != null) {
                String ext = rawExtends.trim().split("[,<{\\s]")[0].trim();
                def.setParentClass(resolveType(ext, importMap, packageName));
            }

            // implements
            String rawImplements = matchFirst(IMPLEMENTS_PATTERN, content);
            if (rawImplements != null) {
                for (String iface : rawImplements.split(",")) {
                    String clean = iface.trim().split("[<{\\s]")[0].trim();
                    if (!clean.isBlank())
                        def.getInterfaces().add(resolveType(clean, importMap, packageName));
                }
            }

            // methods, setters, thrown exceptions
            Matcher mm = METHOD_PATTERN.matcher(content);
            while (mm.find()) {
                String name = mm.group(1);
                if (name == null || name.isBlank()) continue;
                def.getMethodNames().add(name);
                if (name.startsWith("set") && name.length() > 3)
                    def.getSetterNames().add(name);
                String throwsClause = mm.group(3);
                if (throwsClause != null) {
                    for (String ex : throwsClause.split(","))
                        def.getThrownExceptions().add(ex.trim());
                }
            }

            // behavior types
            inferBehaviorTypes(def, content);

            // return codes: static final int constants
            Map<String, String> constants = new LinkedHashMap<>();
            Matcher cm = INT_CONSTANT_PATTERN.matcher(content);
            while (cm.find()) {
                constants.put(cm.group(1), cm.group(2));
            }

            // return codes from Javadoc
            Matcher jdm = JAVADOC_PATTERN.matcher(content);
            while (jdm.find()) {
                String docText = jdm.group(1);
                Matcher rcm = JAVADOC_RETURN_CODE_PATTERN.matcher(docText);
                while (rcm.find()) {
                    String code    = rcm.group(1);
                    String meaning = rcm.group(2) != null ? rcm.group(2) : rcm.group(3);
                    if (meaning != null) def.addReturnCode(code, meaning.trim());
                }
            }

            // return codes from return statements
            Matcher rm = RETURN_PATTERN.matcher(content);
            while (rm.find()) {
                String val = rm.group(1);
                if (val.matches("-?\\d+")) {
                    def.addReturnCode(val, "");
                } else if (constants.containsKey(val)) {
                    String resolved = constants.get(val);
                    String meaning  = val.toLowerCase().replace("_", " ");
                    def.addReturnCode(resolved, meaning);
                }
            }

            // thrown exceptions from throw new statements
            Matcher tnm = THROW_NEW_PATTERN.matcher(content);
            while (tnm.find()) def.getThrownExceptions().add(tnm.group(1));

            return def;
        } catch (IOException e) {
            throw new RuntimeException("Failed parsing Java: " + javaFile, e);
        }
    }

    // -- helpers --------------------------------------------------------------

    private void inferBehaviorTypes(JavaClassDef def, String content) {
        String lower = content.toLowerCase();
        String fqcn  = def.getFullyQualifiedName().toLowerCase();
        if (lower.contains("java.sql") || lower.contains("callablestatement")
                || lower.contains("preparestatement") || lower.contains("storedprocedure")
                || lower.contains("jdbctemplate"))
            def.getBehaviorTypes().add("db_accessor");
        if (fqcn.contains("error") || fqcn.contains("maperror")
                || lower.contains("errorcategory") || lower.contains("errornumber"))
            def.getBehaviorTypes().add("error_mapper");
        if (fqcn.contains("validator") || fqcn.contains("validate")
                || lower.contains("mandatory") || lower.contains("isnull"))
            def.getBehaviorTypes().add("validator");
        if (fqcn.contains("format") || fqcn.contains("decorator")
                || def.getSetterNames().stream().anyMatch(
                    s -> s.contains("Pattern") || s.contains("DataName") || s.contains("Sep")))
            def.getBehaviorTypes().add("formatter");
        if (fqcn.contains("collect") || fqcn.contains("icoll") || fqcn.contains("coll"))
            def.getBehaviorTypes().add("collector");
        if (def.getBehaviorTypes().isEmpty())
            def.getBehaviorTypes().add("unknown");
    }

    /** Resolves a simple class name to FQCN using the import map, falling back to same package. */
    private String resolveType(String simpleName, Map<String, String> importMap, String pkg) {
        if (simpleName.contains(".")) return simpleName; // already qualified
        if (importMap.containsKey(simpleName)) return importMap.get(simpleName);
        if (pkg != null && !pkg.isBlank()) return pkg + "." + simpleName;
        return simpleName;
    }

    private String matchFirst(Pattern p, String text) {
        Matcher m = p.matcher(text);
        return m.find() ? m.group(1) : null;
    }
}
