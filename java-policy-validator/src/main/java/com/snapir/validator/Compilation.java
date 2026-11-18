package com.snapir.validator;
import com.fasterxml.jackson.databind.JsonNode;
import javax.tools.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.jar.JarFile;

/** Mandatory isolated javac check; no processors, Maven plugins or candidate code are executed. */
final class Compilation {
    static Map<String,Object> check(List<Path> candidateSources, Map<Path,String> names,
            JsonNode context, Path policyPath, Report report) throws Exception {
        if (!context.isObject() || context.has("source_roots") && !context.path("source_roots").isArray())
            throw new IllegalArgumentException("Compilation inputs must be an object with a source_roots array");
        if (report.policy.has("target_java_version") && !report.policy.path("target_java_version").isIntegralNumber())
            throw new IllegalArgumentException("target_java_version must be an integer");
        int release = context.path("release").asInt(report.policy.path("target_java_version").asInt(17));
        if (release < 17) throw new IllegalArgumentException("Compilation requires release 17 or later");
        if (context.has("release") && !context.get("release").isIntegralNumber())
            throw new IllegalArgumentException("Compilation release must be an integer");
        var sources = new ArrayList<Path>(candidateSources);
        var supportHashes = new TreeMap<String,String>();
        var inputHashes = new LinkedHashMap<Path,String>();
        for (Path path : candidateSources) inputHashes.put(path,hash(path));
        int index=0;
        for (JsonNode supplied : context.path("source_roots")) {
            if (!supplied.isTextual() || supplied.asText().isBlank())
                throw new IllegalArgumentException("Support source roots must be nonempty paths");
            Path root=Path.of(supplied.asText()).toAbsolutePath().normalize();
            if (!Files.isDirectory(root) || Files.isSymbolicLink(root))
                throw new IllegalArgumentException("Invalid support source root: "+root);
            try (var files=Files.walk(root)) {
                for (Path path:files.sorted().toList()) {
                    if (Files.isSymbolicLink(path)) throw new IllegalArgumentException("Support symlink: "+path);
                    if (!Files.isRegularFile(path) || !path.toString().endsWith(".java")) continue;
                    String name="support/"+index+"/"+root.relativize(path).toString().replace('\\','/');
                    String fingerprint=hash(path); supportHashes.put(name,fingerprint); inputHashes.put(path,fingerprint);
                    names.put(path,name); sources.add(path);
                    JavaChecks.check(name,Files.readString(path,StandardCharsets.UTF_8).replaceFirst("^\\uFEFF",""),report);
                }
            }
            index++;
        }
        var jars = new ArrayList<Path>();
        var jarHashes = new TreeMap<String,String>();
        if (report.policy.has("compile_classpath") && !report.policy.path("compile_classpath").isArray())
            throw new IllegalArgumentException("compile_classpath must be an array");
        for (JsonNode entry:report.policy.path("compile_classpath")) {
            String coordinate=entry.path("coordinate").asText();
            if (!report.allowed("allowed_dependencies",coordinate))
                throw new IllegalArgumentException("Compilation dependency is not approved: "+coordinate);
            Path jar=policyPath.toAbsolutePath().getParent().resolve(entry.path("path").asText()).normalize();
            if (!Files.isRegularFile(jar) || Files.isSymbolicLink(jar) || !jar.toString().endsWith(".jar")
                || !entry.path("sha256").asText().equals(hash(jar)))
                throw new IllegalArgumentException("Compilation JAR is missing or its hash differs: "+jar);
            try (var archive=new JarFile(jar.toFile())) {
                if (archive.getManifest()!=null && archive.getManifest().getMainAttributes().getValue("Class-Path")!=null)
                    throw new IllegalArgumentException("Compilation JAR has an implicit manifest classpath: "+jar);
                var entries=archive.entries();
                while (entries.hasMoreElements()) {
                    String name=entries.nextElement().getName().replaceFirst("^META-INF/versions/[0-9]+/","");
                    if (name.endsWith(".class") && report.matches("forbidden_packages",name.replace('/', '.').replaceAll("\\.class$","")))
                        throw new IllegalArgumentException("Compilation JAR contains forbidden framework classes: "+jar);
                }
            }
            jars.add(jar); jarHashes.put(jar.toString(),hash(jar)); inputHashes.put(jar,hash(jar));
        }
        var result=new LinkedHashMap<String,Object>();
        result.put("release",release);result.put("support_files",supportHashes);result.put("classpath_files",jarHashes);
        var diagnostics = new DiagnosticCollector<JavaFileObject>();
        var compiler=ToolProvider.getSystemJavaCompiler();
        if (compiler==null) throw new IllegalStateException("Full JDK required: javac is unavailable");
        Path temporary=Files.createTempDirectory("java-policy-compile-");
        try {
            if (candidateSources.isEmpty()) {
                report.add("compilation", "", 0,"", "No candidate Java source files were supplied.","Supply the generated Java source files.");
                result.put("status","failed");result.put("diagnostics",List.of());return result;
            }
            Path output=Files.createDirectory(temporary.resolve("classes"));
            Path empty=Files.createDirectory(temporary.resolve("empty"));
            String classpath=jars.isEmpty()?empty.toString():String.join(java.io.File.pathSeparator,jars.stream().map(Object::toString).toList());
            try (var manager=compiler.getStandardFileManager(diagnostics,Locale.ROOT,StandardCharsets.UTF_8)) {
                var options=List.of("--release",Integer.toString(release),"-proc:none","-implicit:none",
                    "--class-path",classpath,"--source-path",empty.toString(),"--processor-path",empty.toString(),
                    "-encoding","UTF-8","-d",output.toString());
                boolean passed=Boolean.TRUE.equals(compiler.getTask(null,manager,diagnostics,options,null,
                    manager.getJavaFileObjectsFromPaths(sources)).call());
                var messages=new ArrayList<Map<String,Object>>();
                for (var diagnostic:diagnostics.getDiagnostics()) {
                    Path path=diagnostic.getSource()==null?null:Path.of(diagnostic.getSource().toUri()).toAbsolutePath().normalize();
                    String name=path==null?"":names.getOrDefault(path,path.toString());
                    String message=diagnostic.getMessage(Locale.ROOT);
                    messages.add(Map.of("file",name,"line",diagnostic.getLineNumber(),"column",diagnostic.getColumnNumber(),
                        "code",diagnostic.getCode(),"severity",diagnostic.getKind().name(),"message",message));
                    if (diagnostic.getKind()==Diagnostic.Kind.ERROR) report.add("compilation",name,
                        (int)Math.max(0,diagnostic.getLineNumber()),diagnostic.getCode(),message,
                        "Correct the Java types, signatures and interface implementations; supply required approved native dependencies.");
                }
                result.put("status",passed?"passed":"failed");result.put("diagnostics",messages);
                if (!passed && diagnostics.getDiagnostics().isEmpty())
                    report.add("compilation","",0,"","javac did not succeed.","Inspect compiler configuration and return compilable Java.");
            }
            for (var entry:inputHashes.entrySet()) if (!hash(entry.getKey()).equals(entry.getValue()))
                throw new IllegalStateException("Compilation input changed: "+entry.getKey());
            return result;
        } finally {
            try (var paths=Files.walk(temporary)) {
                for (Path path:paths.sorted(Comparator.reverseOrder()).toList()) Files.delete(path);
            }
        }
    }
    private static String hash(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }
}
