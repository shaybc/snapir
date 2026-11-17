package com.snapir.validator;
import com.github.javaparser.*;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import java.util.*;

/** Syntax and dependency checks on AST nodes, never comments or ordinary literals. */
final class JavaChecks {
    private static final Set<String> LOOKUPS = Set.of("forName", "getClassLoader", "getDeclaredMethod",
        "getDeclaredMethods", "getDeclaredField", "getDeclaredFields", "getDeclaredConstructor",
        "getDeclaredConstructors", "getMethod", "getMethods", "getField", "getFields",
        "getConstructor", "getConstructors", "newInstance");
    static void check(String file, String content, Report report) {
        var parser = new JavaParser(new ParserConfiguration()
            .setPreprocessUnicodeEscapes(true).setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
        var parsed = parser.parse(content);
        if (!parsed.isSuccessful()) {
            for (var problem : parsed.getProblems()) report.add("java_syntax",file,
                problem.getLocation().flatMap(range -> range.getBegin().getRange()).map(range -> range.begin.line).orElse(0),
                "", problem.getMessage(), "Return complete syntactically valid Java source.");
            return;
        }
        var unit = parsed.getResult().orElseThrow();
        Set<String> classValues = new HashSet<>(Set.of("Class"));
        unit.findAll(com.github.javaparser.ast.body.VariableDeclarator.class).forEach(variable -> {
            if (variable.getType().asString().matches("(?:java.lang.)?Class(?:<.*>)?")
                || variable.getInitializer().map(value -> value instanceof ClassExpr || value.toString().contains("getClass()")).orElse(false))
                classValues.add(variable.getNameAsString());
        });
        unit.findAll(com.github.javaparser.ast.body.Parameter.class).forEach(parameter -> {
            if (parameter.getType().asString().matches("(?:java.lang.)?Class(?:<.*>)?")) classValues.add(parameter.getNameAsString());
        });
        for (Node node : unit.findAll(Node.class)) {
            String reference = null;
            if (node instanceof Name name) reference = name.asString();
            else if (node instanceof ClassOrInterfaceType type) reference = type.getNameWithScope();
            else if (node instanceof FieldAccessExpr access) reference = access.toString();
            else if (node instanceof NameExpr name) reference = name.getNameAsString();
            if (reference != null && report.matches("forbidden_packages",reference))
                finding(report,"forbidden_java_dependency",file,node,reference,"IBM/Composer or prohibited framework reference",
                    "Replace framework types and delegation with native Java and explicit native interfaces.");
            if (reference != null && (report.matches("forbidden_reflection_packages",reference)
                || reference.equals("ClassLoader") || reference.endsWith(".ClassLoader")))
                finding(report,"reflection",file,node,reference,"Reflective or dynamic runtime API",
                    "Use direct typed calls or an evidence-based typed dispatcher.");
            if (node instanceof MethodCallExpr call) {
                String scope = call.getScope().map(Object::toString).orElse("");
                String method = call.getNameAsString();
                if (method.equals("loadClass") || method.equals("defineClass") || method.equals("forName")
                    || method.equals("getClassLoader") || method.startsWith("getDeclared")
                    || LOOKUPS.contains(method) && (classValues.contains(scope) || scope.equals("java.lang.Class")
                        || scope.endsWith(".class") || scope.endsWith("getClass()"))
                    || method.equals("load") && (scope.equals("ServiceLoader") || scope.equals("java.util.ServiceLoader")))
                    finding(report,"reflection",file,node,call.toString(),"Dynamic class loading or reflective lookup",
                        "Replace dynamic lookup with explicit native types and calls.");
            }
            if (node instanceof MethodReferenceExpr ref && (LOOKUPS.contains(ref.getIdentifier())
                && (classValues.contains(ref.getScope().toString()) || ref.getScope().toString().equals("java.lang.Class")
                    || ref.getScope().toString().endsWith(".class"))
                || Set.of("loadClass","defineClass").contains(ref.getIdentifier())))
                finding(report,"reflection",file,node,ref.toString(),"Potential reflective method reference",
                    "Use an explicit typed native call.");
        }
    }
    private static void finding(Report report,String rule,String file,Node node,String reference,String message,String fix) {
        report.add(rule,file,node.getBegin().map(p -> p.line).orElse(0),reference,message,fix);
    }
}
