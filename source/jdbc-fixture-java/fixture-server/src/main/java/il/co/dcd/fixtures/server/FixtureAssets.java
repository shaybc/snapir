package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.*;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Read-only verification and strict reference resolution for existing Python-published banks. */
public final class FixtureAssets {
    private final List<Path> roots;
    public FixtureAssets(List<Path> allowedRoots) throws IOException {
        roots=new ArrayList<>();for (Path root : allowedRoots) roots.add(root.toRealPath());
        if (roots.isEmpty()) throw new IllegalArgumentException("At least one fixture root is required");
    }
    private Path allowed(Path path) throws IOException {
        Path real=path.toRealPath();
        if (roots.stream().noneMatch(real::startsWith)) throw new IllegalArgumentException("Fixture path outside allowed roots");
        return real;
    }
    public Map<String,Object> load(Path directory,String expectedHash) throws IOException {
        Path root=allowed(directory),manifestPath=allowed(root.resolve("manifest.json"));
        if(!manifestPath.getParent().equals(root) || Files.size(manifestPath)>Json.MAX_BYTES)throw new IllegalArgumentException("Invalid manifest path or size");
        Map<String,Object> manifest=Json.object(Json.read(Files.readAllBytes(manifestPath)));
        Json.keys(manifest,"schema_version","boundary_identity","revision","context_hash","files");
        if (!"test-assets-v1".equals(manifest.get("schema_version")) || !Json.digest(manifest).equals(expectedHash))
            throw new IllegalArgumentException("Test asset manifest identity changed");
        Map<String,Object> files=Json.object(manifest.get("files"));
        Set<String> required=Set.of("fixtures.json","junit-scenarios.json","comparison-scenarios.json");
        if (!files.keySet().containsAll(required) || !Set.of("fixtures.json","junit-scenarios.json","comparison-scenarios.json","validation.json").containsAll(files.keySet()))
            throw new IllegalArgumentException("Unexpected test asset documents");
        Map<String,Object> documents=new LinkedHashMap<>();
        for (var entry : files.entrySet()) {
            Path path=allowed(root.resolve(entry.getKey()));
            if (!path.getParent().equals(root)) throw new IllegalArgumentException("Asset document escaped its revision");
            if (Files.size(path)>Json.MAX_BYTES) throw new IllegalArgumentException("Asset document exceeds byte limit");
            byte[] bytes=Files.readAllBytes(path);
            if (!Json.hash(bytes).equals(entry.getValue())) throw new IllegalArgumentException("Test asset document changed");
            documents.put(entry.getKey(),Json.read(bytes));
        }
        Map<String,Object> bank=Json.object(documents.get("fixtures.json"));
        Json.keys(bank,"schema_version","fixtures","unresolved");
        if (!"shared-fixtures-v1".equals(bank.get("schema_version"))) throw new IllegalArgumentException("Unsupported fixture bank schema");
        if (!((List<?>)bank.getOrDefault("unresolved",List.of())).isEmpty()) throw new IllegalArgumentException("Fixture bank has unresolved inputs");
        for(var entry:Json.object(bank.get("fixtures")).entrySet()) {
            if(!entry.getKey().matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,95}"))throw new IllegalArgumentException("Invalid fixture ID");
            Map<String,Object> fixture=Json.object(entry.getValue());Json.keys(fixture,"kind","value","origin","citations");
            if(!fixture.containsKey("value") || !Set.of("value","xml","context","database","service").contains(fixture.getOrDefault("kind","value")))throw new IllegalArgumentException("Invalid fixture definition");
        }
        return bank;
    }
    public static Object resolve(Map<String,Object> bank,String id,String pointer) {
        return resolve(bank,id,pointer,new HashSet<>());
    }
    private static Object resolve(Map<String,Object> bank,String id,String pointer,Set<String> active) {
        if (!id.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")) throw new IllegalArgumentException("Invalid fixture ID");
        if (active.size()>=100 || !active.add(id)) throw new IllegalArgumentException("Cyclic or excessively deep fixture reference");
        try {
            Map<String,Object> fixtures=Json.object(bank.get("fixtures"));
            if (!fixtures.containsKey(id)) throw new IllegalArgumentException("Missing fixture ID");
            Object value=visit(bank,Json.object(fixtures.get(id)).get("value"),active);
            return pointer(value,pointer);
        } finally { active.remove(id); }
    }
    private static Object visit(Map<String,Object> bank,Object value,Set<String> active) {
        if (value instanceof Map<?,?>) {
            Map<String,Object> map=Json.object(value);
            if (map.containsKey("$fixture")) {
                Json.keys(map,"$fixture","pointer");
                return resolve(bank,(String)map.get("$fixture"),(String)map.getOrDefault("pointer",""),active);
            }
            Map<String,Object> out=new LinkedHashMap<>();map.forEach((k,v)->out.put(k,visit(bank,v,active)));return out;
        }
        if (value instanceof List<?> list) return list.stream().map(v->visit(bank,v,active)).toList();
        return value;
    }
    private static Object pointer(Object value,String pointer) {
        if (pointer.isEmpty()) return value;
        if (!pointer.startsWith("/") || pointer.matches(".*~(?![01]).*")) throw new IllegalArgumentException("Invalid JSON pointer");
        for (String part : pointer.substring(1).split("/",-1)) {
            String key=part.replace("~1","/").replace("~0","~");
            if (value instanceof Map<?,?> map && map.containsKey(key)) value=map.get(key);
            else if (value instanceof List<?> list && key.matches("0|[1-9][0-9]*")) {
                try { value=list.get(Integer.parseInt(key)); }
                catch (IndexOutOfBoundsException | NumberFormatException e) { throw new IllegalArgumentException("Missing fixture array element"); }
            } else throw new IllegalArgumentException("Missing fixture pointer");
        }
        return value;
    }
}
