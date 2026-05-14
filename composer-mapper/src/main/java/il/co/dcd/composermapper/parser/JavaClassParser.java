package il.co.dcd.composermapper.parser;

import il.co.dcd.composermapper.model.JavaClassDef;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class JavaClassParser {
    private static final Pattern PACKAGE_PATTERN = Pattern.compile("(?m)^\\s*package\\s+([a-zA-Z0-9_.]+)\\s*;");
    private static final Pattern IMPORT_PATTERN = Pattern.compile("(?m)^\\s*import\\s+([a-zA-Z0-9_.*]+)\\s*;");
    private static final Pattern CLASS_PATTERN = Pattern.compile("(?m)^\\s*(?:public\\s+)?(?:abstract\\s+|final\\s+)?(?:class|interface|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)\\b");
    private static final Pattern METHOD_PATTERN = Pattern.compile("(?m)^\\s*(?:public|protected|private)?\\s*(?:static\\s+)?(?:final\\s+)?(?:synchronized\\s+)?(?:[A-Za-z_][A-Za-z0-9_<>\\[\\], ?]+)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^)]*)\\)\\s*(?:throws\\s+([^\\{]+))?\\{");
    private static final Pattern INT_CONSTANT_PATTERN = Pattern.compile("(?m)^\\s*(?:public|protected|private)?\\s*static\\s+final\\s+int\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(-?\\d+)\\s*;");
    private static final Pattern RETURN_PATTERN = Pattern.compile("\\breturn\\s+(-?\\d+|[A-Za-z_][A-Za-z0-9_]*)\\s*;");
    private static final Pattern THROW_NEW_PATTERN = Pattern.compile("\\bthrow\\s+new\\s+([A-Za-z_][A-Za-z0-9_.$]*)\\s*\\(");
    private static final Pattern JAVADOC_PATTERN = Pattern.compile("(?s)/\\*\\*(.*?)\\*/");
    private static final Pattern JAVADOC_RETURN_CODE_PATTERN = Pattern.compile("(?i)(?:returns?\\s*)?(-?\\d+)\\s*(?:\\(([^)]+)\\)|[-:=]\\s*([^,;\\n\\r.]+))");

    public JavaClassDef parse(Path javaFile) {
        try {
            String content = Files.readString(javaFile, StandardCharsets.UTF_8);
            String packageName = matchFirst(PACKAGE_PATTERN, content);
            String simpleName = matchFirst(CLASS_PATTERN, content);
            if (simpleName == null || simpleName.isBlank()) {
                return null;
            }

            JavaClassDef def = new JavaClassDef();
            def.setSourceFile(javaFile);
            def.setPackageName(packageName == null ? "" : packageName);
            def.setSimpleName(simpleName);
            def.setFullyQualifiedName(def.getPackageName().isBlank() ? simpleName : def.getPackageName() + "." + simpleName);

            Matcher importMatcher = IMPORT_PATTERN.matcher(content);
            while (importMatcher.find()) {
                String imp = importMatcher.group(1);
                def.getImports().add(imp);
                inferImportDependency(imp, def);
            }

            Matcher methodMatcher = METHOD_PATTERN.matcher(content);
            while (methodMatcher.find()) {
                String methodName = methodMatcher.group(1);
                String params = methodMatcher.group(2) == null ? "" : methodMatcher.group(2).trim();
                String throwsClause = methodMatcher.group(3) == null ? "" : methodMatcher.group(3).trim();
                def.getMethodNames().add(methodName);
                if (methodName.startsWith("set") && parameterCount(params) == 1) {
                    def.getSetterNames().add(methodName);
                }
                captureThrowsClause(throwsClause, def);
                inferMethodDependency(methodName, def);
            }

            inferBodyDependencies(content, def);
            inferThrownExceptions(content, def);
            inferReturnCodes(content, def);
            inferBehaviorTypes(content, def);
            return def;
        } catch (IOException e) {
            throw new RuntimeException("Failed parsing Java: " + javaFile, e);
        }
    }

    private String matchFirst(Pattern pattern, String text) {
        Matcher matcher = pattern.matcher(text);
        return matcher.find() ? matcher.group(1) : null;
    }

    private int parameterCount(String params) {
        if (params == null || params.isBlank()) {
            return 0;
        }
        int count = 1;
        int genericDepth = 0;
        for (int i = 0; i < params.length(); i++) {
            char ch = params.charAt(i);
            if (ch == '<') genericDepth++;
            else if (ch == '>') genericDepth = Math.max(0, genericDepth - 1);
            else if (ch == ',' && genericDepth == 0) count++;
        }
        return count;
    }

    private void inferMethodDependency(String methodName, JavaClassDef def) {
        String lower = methodName.toLowerCase();
        if (lower.contains("executequery") || lower.contains("preparestatement") || lower.contains("callable") || lower.contains("jdbc")) {
            def.getInferredExternalDependencies().add("Database");
        }
        if (lower.contains("post") || lower.contains("get") || lower.contains("send") || lower.contains("invoke") || lower.contains("request")) {
            def.getInferredExternalDependencies().add("Possible API/Service call");
        }
    }

    private void inferImportDependency(String importName, JavaClassDef def) {
        String lower = importName.toLowerCase();
        if (lower.startsWith("com.ibm.") || lower.equals("com.ibm")) {
            def.getInferredExternalDependencies().add("IBM/WAS");
        }
        if (lower.contains("java.sql") || lower.contains("jdbc")) {
            def.getInferredExternalDependencies().add("Database");
        }
        if (lower.contains("http") || lower.contains("soap") || lower.contains("rest") || lower.contains("ws")) {
            def.getInferredExternalDependencies().add("API/Service");
        }
    }

    private void inferBodyDependencies(String content, JavaClassDef def) {
        String lower = content.toLowerCase();
        if (lower.contains("preparestatement(") || lower.contains("executequery(") || lower.contains("executecall(") || lower.contains("callablestatement")) {
            def.getInferredExternalDependencies().add("Database");
        }
        if (lower.contains("http://") || lower.contains("https://") || lower.contains("soap") || lower.contains("resttemplate") || lower.contains("webservice") || lower.contains("urlconnection")) {
            def.getInferredExternalDependencies().add("API/Service");
        }
    }

    private void captureThrowsClause(String throwsClause, JavaClassDef def) {
        if (throwsClause == null || throwsClause.isBlank()) return;

        for (String exception : throwsClause.split(",")) {
            String cleaned = exception.trim();
            if (!cleaned.isBlank()) def.getThrownExceptions().add(cleaned);
        }
    }

    private void inferThrownExceptions(String content, JavaClassDef def) {
        Matcher matcher = THROW_NEW_PATTERN.matcher(content);
        while (matcher.find()) {
            def.getThrownExceptions().add(matcher.group(1));
        }
    }

    private void inferBehaviorTypes(String content, JavaClassDef def) {
        String className = def.getSimpleName() == null ? "" : def.getSimpleName();
        String lowerClass = className.toLowerCase();
        String lowerContent = content.toLowerCase();

        if (def.getInferredExternalDependencies().contains("Database")
                || hasSetter(def, "setStoredProcedure")
                || hasSetter(def, "setFromTable")
                || hasSetter(def, "setFromColumn")
                || hasSetter(def, "setKeyValue")
                || lowerClass.contains("tableformat")
                || lowerClass.endsWith("sp")
                || lowerContent.contains("preparestatement(")
                || lowerContent.contains("executequery(")) {
            def.getBehaviorTypes().add("db_accessor");
        }

        if (hasAnySetter(def, "setPattern", "setUseSep", "setDataName", "setTransparent", "setUnnamed")
                || lowerClass.startsWith("cc")
                || lowerClass.endsWith("format")) {
            def.getBehaviorTypes().add("formatter");
        }

        if (lowerClass.contains("error") || hasMethodContaining(def, "maperror") || hasAnySetter(def, "setErrorCategory", "setErrorNumber")) {
            def.getBehaviorTypes().add("error_mapper");
        }

        if (lowerClass.startsWith("validate") || lowerClass.contains("validator") || hasMethodContaining(def, "validate")) {
            def.getBehaviorTypes().add("validator");
        }

        if (lowerClass.contains("collector") || lowerClass.contains("collection") || lowerClass.contains("tcoll") || hasMethodContaining(def, "collect")) {
            def.getBehaviorTypes().add("collector");
        }

        if (lowerClass.contains("operationstep") || lowerClass.contains("flow") || lowerClass.contains("route")
                || hasMethodContaining(def, "transition") || hasMethodContaining(def, "route")) {
            def.getBehaviorTypes().add("flow_control");
        }

        if (def.getBehaviorTypes().isEmpty()) {
            def.getBehaviorTypes().add("unknown");
        }
    }

    private boolean hasAnySetter(JavaClassDef def, String... setters) {
        for (String setter : setters) {
            if (hasSetter(def, setter)) return true;
        }
        return false;
    }

    private boolean hasSetter(JavaClassDef def, String setter) {
        return def.getSetterNames().stream().anyMatch(s -> s.equalsIgnoreCase(setter));
    }

    private boolean hasMethodContaining(JavaClassDef def, String needle) {
        String lowerNeedle = needle.toLowerCase();
        return def.getMethodNames().stream().anyMatch(m -> m.toLowerCase().contains(lowerNeedle));
    }

    private void inferReturnCodes(String content, JavaClassDef def) {
        Map<String, String> constants = new LinkedHashMap<>();
        Matcher constantMatcher = INT_CONSTANT_PATTERN.matcher(content);
        while (constantMatcher.find()) {
            String name = constantMatcher.group(1);
            String code = constantMatcher.group(2);
            constants.put(name, code);
            def.addReturnCode(code, humanizeConstant(name));
        }

        Matcher javadocMatcher = JAVADOC_PATTERN.matcher(content);
        while (javadocMatcher.find()) {
            captureJavadocReturnCodes(javadocMatcher.group(1), def);
        }

        Matcher returnMatcher = RETURN_PATTERN.matcher(content);
        while (returnMatcher.find()) {
            String returned = returnMatcher.group(1);
            String code = constants.getOrDefault(returned, returned);
            String meaning = constants.containsKey(returned) ? humanizeConstant(returned) : defaultMeaning(code);
            def.addReturnCode(code, meaning);
        }
    }

    private void captureJavadocReturnCodes(String comment, JavaClassDef def) {
        String text = comment
                .replaceAll("(?m)^\\s*\\*\\s?", "")
                .replaceAll("\\s+", " ")
                .trim();
        Matcher matcher = JAVADOC_RETURN_CODE_PATTERN.matcher(text);
        while (matcher.find()) {
            String meaning = matcher.group(2) != null ? matcher.group(2) : matcher.group(3);
            def.addReturnCode(matcher.group(1), meaning == null ? defaultMeaning(matcher.group(1)) : meaning.trim());
        }
    }

    private String defaultMeaning(String code) {
        return "0".equals(code) ? "success" : "observed return code";
    }

    private String humanizeConstant(String name) {
        String normalized = name
                .replaceFirst("(?i)^(return|rc|code|status)_?", "")
                .replace('_', ' ')
                .trim()
                .toLowerCase();
        return normalized.isBlank() ? name : normalized;
    }
}
