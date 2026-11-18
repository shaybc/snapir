package com.snapir.validator;
import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.nio.charset.StandardCharsets;

/** Independent CLI: Main CODE_PATH POLICY_JSON; stdout is exactly one JSON report. */
public final class Main {
    public static void main(String[] args) throws Exception {
        var json = new ObjectMapper();
        var output = new LinkedHashMap<String,Object>();
        output.put("schema_version","java-policy-validation-v1"); output.put("tool_version","1.1.0");
        output.put("checks",List.of("java_syntax","java_dependencies","reflection","maven","runtime_registrations","compilation"));
        output.put("limitations",List.of("No execution, transitive Maven resolution or behavioral verification.",
            "Compilation uses only supplied native support sources and policy-approved JARs; annotation processing is disabled."));
        int exit=2;
        try {
            if (args.length<2 || args.length>3) throw new IllegalArgumentException("Expected CODE_PATH POLICY_JSON [COMPILATION_INPUTS_JSON]");
            var context=args.length==3?json.readTree(Path.of(args[2]).toFile()):json.createObjectNode();
            byte[] policyBytes=Files.readAllBytes(Path.of(args[1]));
            var policy=json.readTree(policyBytes);
            if (!policy.path("version").isTextual()) throw new IllegalArgumentException("Policy version is required");
            for (String key:List.of("forbidden_packages","forbidden_reflection_packages","allowed_dependencies","allowed_plugins","allowed_repositories")) {
                if (!policy.path(key).isArray()) throw new IllegalArgumentException("Policy array required: "+key);
                for (var value:policy.path(key)) if (!value.isTextual() || value.asText().isBlank())
                    throw new IllegalArgumentException("Invalid policy value: "+key);
            }
            output.put("policy_version",policy.path("version").asText());output.put("policy_hash",hash(policyBytes));
            var report=new Report(policy);
            Path root=Path.of(args[0]).toAbsolutePath().normalize();
            if (!Files.exists(root)) throw new IllegalArgumentException("Code path does not exist: "+root);
            var hashes=new TreeMap<String,String>();
            var sources=new ArrayList<Path>();
            var names=new HashMap<Path,String>();
            try (var paths=Files.isDirectory(root)?Files.walk(root):java.util.stream.Stream.of(root)) {
                for (Path path:paths.sorted().toList()) {
                    if (Files.isSymbolicLink(path)) throw new IllegalArgumentException("Symbolic links are not accepted: "+path);
                    if (!Files.isRegularFile(path)) continue;
                    String name=Files.isDirectory(root)?root.relativize(path).toString().replace('\\','/'):path.getFileName().toString();
                    byte[] bytes=Files.readAllBytes(path);hashes.put(name,hash(bytes));
                    if (name.endsWith(".jar") || name.endsWith(".class")) {
                        report.add("opaque_binary",name,0,name,"Binary dependencies cannot be inspected as generated source.","Supply native source and approved Maven declarations.");continue;
                    }
                    if (!name.endsWith(".java") && !name.endsWith(".xml") && !name.contains("META-INF/services/")) continue;
                    String content=StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(bytes)).toString().replaceFirst("^\\uFEFF","");
                    if (name.endsWith(".java")) {
                        sources.add(path); names.put(path,name); JavaChecks.check(name,content,report);
                    }
                    else ProjectChecks.check(name,content,report);
                }
            }
            if (hashes.isEmpty()) throw new IllegalArgumentException("No files to validate");
            output.put("files",hashes);output.put("input_hash",hash(json.writeValueAsBytes(hashes)));
            output.put("compilation",Compilation.check(sources,names,context,Path.of(args[1]),report));
            output.put("findings",report.findings);output.put("status",report.findings.isEmpty()?"passed":"failed");
            exit=report.findings.isEmpty()?0:1;
        } catch (Exception error) {
            output.put("status","error");output.put("findings",List.of());output.put("error",error.toString());
            System.err.println("Validator failed: "+error);
        }
        System.out.println(json.writeValueAsString(output));System.exit(exit);
    }
    private static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
