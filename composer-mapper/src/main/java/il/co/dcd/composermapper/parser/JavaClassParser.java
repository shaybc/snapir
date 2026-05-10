package il.co.dcd.composermapper.parser;

import il.co.dcd.composermapper.model.JavaClassDef;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class JavaClassParser {
    private static final Pattern PACKAGE_PATTERN = Pattern.compile("(?m)^\\s*package\\s+([a-zA-Z0-9_.]+)\\s*;");
    private static final Pattern IMPORT_PATTERN = Pattern.compile("(?m)^\\s*import\\s+([a-zA-Z0-9_.*]+)\\s*;");
    private static final Pattern CLASS_PATTERN = Pattern.compile("(?m)^\\s*(?:public\\s+)?(?:abstract\\s+|final\\s+)?(?:class|interface|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)\\b");
    private static final Pattern METHOD_PATTERN = Pattern.compile("(?m)^\\s*(?:public|protected|private)?\\s*(?:static\\s+)?(?:final\\s+)?(?:synchronized\\s+)?(?:[A-Za-z_][A-Za-z0-9_<>\\[\\], ?]+)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\(([^)]*)\\)\\s*(?:throws [^{]+)?\\{");

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
                def.getMethodNames().add(methodName);
                if (methodName.startsWith("set") && parameterCount(params) == 1) {
                    def.getSetterNames().add(methodName);
                }
                inferMethodDependency(methodName, def);
            }

            inferBodyDependencies(content, def);
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
}
