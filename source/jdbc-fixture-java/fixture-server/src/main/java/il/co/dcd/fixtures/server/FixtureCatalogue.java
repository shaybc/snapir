package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.*;
import il.co.dcd.fixtures.replay.Replay;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/** Freeze reference-only catalogue data after validating every referenced immutable revision. */
public final class FixtureCatalogue {
    public final String hash;
    private final Map<String,Map<String,List<Map<String,Object>>>> scenarios=new LinkedHashMap<>();
    public FixtureCatalogue(Path path,String expectedHash,List<Path> roots) throws IOException {
        this(path,expectedHash,roots,Map.of());
    }
    @SuppressWarnings("unchecked") public FixtureCatalogue(Path path,String expectedHash,List<Path> roots,Map<String,Path> relocations) throws IOException {
        if (Files.size(path)>Json.MAX_BYTES) throw new IllegalArgumentException("Catalogue byte limit exceeded");
        Map<String,Object> catalogue=Json.object(Json.read(Files.readAllBytes(path)));
        Json.keys(catalogue,"schema_version","scenarios");hash=Json.digest(catalogue);
        if (!hash.equals(expectedHash) || !"fixture-jdbc-catalogue-v1".equals(catalogue.get("schema_version")))
            throw new IllegalArgumentException("Catalogue identity or schema mismatch");
        FixtureAssets assets=new FixtureAssets(roots);
        Map<String,Object> definitions=Json.object(catalogue.get("scenarios"));
        if (definitions.isEmpty() || definitions.size()>1024) throw new IllegalArgumentException("Invalid catalogue scenario count");
        long loadedBytes=0;int referenceCount=0;
        for (var scenario : definitions.entrySet()) {
            identifier(scenario.getKey());Map<String,Object> spec=Json.object(scenario.getValue());Json.keys(spec,"resources");
            Map<String,List<Map<String,Object>>> resources=new LinkedHashMap<>();
            if(Json.object(spec.get("resources")).size()>64)throw new IllegalArgumentException("Scenario resource count exceeded");
            for (var resource : Json.object(spec.get("resources")).entrySet()) {
                identifier(resource.getKey());Map<String,Object> bindings=Json.object(resource.getValue());Json.keys(bindings,"fixtures");
                List<Map<String,Object>> queries=new ArrayList<>();
                List<?> refs=(List<?>)bindings.get("fixtures");if (refs==null || refs.isEmpty()) throw new IllegalArgumentException("Missing resource fixture references");
                for (Object raw : refs) {
                    Map<String,Object> ref=Json.object(raw);Json.keys(ref,"asset_root","manifest_hash","fixture_id","pointer");
                    if(++referenceCount>512)throw new IllegalArgumentException("Catalogue fixture reference count exceeded");
                    Path assetPath=relocate((String)ref.get("asset_root"),path,relocations);
                    Map<String,Object> bank=assets.load(assetPath,(String)ref.get("manifest_hash"));
                    Object fixture=FixtureAssets.resolve(bank,(String)ref.get("fixture_id"),(String)ref.getOrDefault("pointer",""));
                    loadedBytes+=Json.bytes(fixture).length;
                    if(loadedBytes>4L*Json.MAX_BYTES)throw new IllegalArgumentException("Resolved catalogue byte limit exceeded");
                    Map<String,Object> database=Json.object(Values.decode(fixture));Json.keys(database,"queries");
                    for (Object q : (List<?>)database.get("queries")) {
                        Map<String,Object> query=Json.object(q);validate(query);
                        if(query.get("exception")==null)query.remove("exception");
                        query.putIfAbsent("columns",List.of());query.putIfAbsent("rows",List.of());query.putIfAbsent("out_parameters",Map.of());
                        Map<String,Object> duplicate=Replay.find(queries,(String)query.get("sql"),(List<?>)query.get("parameters"));
                        if (duplicate!=null) {
                            Map<String,Object> a=new LinkedHashMap<>(duplicate),b=new LinkedHashMap<>(query);a.remove("parameters");b.remove("parameters");
                            if (!Json.digest(Values.encode(a)).equals(Json.digest(Values.encode(b)))) throw new IllegalArgumentException("Conflicting fixture SQL/parameter responses");
                        } else queries.add(query);
                        if (queries.size()>10000) throw new IllegalArgumentException("Fixture query count exceeded");
                    }
                }
                resources.put(resource.getKey(),List.copyOf(queries));
            }
            if (resources.isEmpty()) throw new IllegalArgumentException("Scenario has no database resources");
            scenarios.put(scenario.getKey(),Map.copyOf(resources));
        }
    }
    private static Path relocate(String original,Path catalogue,Map<String,Path> relocations) {
        String portable=original.replace('\\','/');
        String prefix=relocations.keySet().stream().filter(p->{String key=p.replace('\\','/').replaceAll("/+$","");return portable.equals(key)||portable.startsWith(key+"/");})
            .max(Comparator.comparingInt(String::length)).orElse(null);
        if(prefix!=null) {
            String key=prefix.replace('\\','/').replaceAll("/+$","");
            String remainder=portable.equals(key) ? "" : portable.substring(key.length()+1);
            return relocations.get(prefix).resolve(remainder);
        }
        return catalogue.toAbsolutePath().getParent().resolve(original);
    }
    private static void identifier(String id) {
        if (!id.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")) throw new IllegalArgumentException("Invalid catalogue ID");
    }
    private static void validate(Map<String,Object> query) {
        Json.keys(query,"sql","parameters","columns","rows","exception","out_parameters");
        if (!(query.get("sql") instanceof String) || !(query.get("parameters") instanceof List<?>)) throw new IllegalArgumentException("SQL and explicit parameters required");
        rows(query);
        if (query.get("exception")!=null) {
            Map<String,Object> failure=Json.object(query.get("exception"));Json.keys(failure,"type","message");
            if (!"java.sql.SQLException".equals(failure.get("type"))) throw new IllegalArgumentException("Unsupported prepared exception");
        }
        for (var entry : Json.object(query.getOrDefault("out_parameters",Map.of())).entrySet()) {
            if (!entry.getKey().matches("[1-9][0-9]*")) throw new IllegalArgumentException("Invalid output index");
            Map<String,Object> output=Json.object(entry.getValue());Json.keys(output,"sql_type","value","columns","rows");
            if (!(output.get("sql_type") instanceof Integer) || output.containsKey("value")==output.containsKey("rows")) throw new IllegalArgumentException("Invalid callable output");
            rows(output);
        }
    }
    private static void rows(Map<String,Object> query) {
        List<?> columns=(List<?>)query.getOrDefault("columns",List.of());
        if (columns.stream().anyMatch(c->!(c instanceof String)) || new HashSet<>(columns).size()!=columns.size()) throw new IllegalArgumentException("Invalid fixture columns");
        List<?> rows=(List<?>)query.getOrDefault("rows",List.of());
        if (rows.size()>10000 || rows.stream().anyMatch(r->!(r instanceof List<?> list) || list.size()!=columns.size())) throw new IllegalArgumentException("Fixture row limit/width mismatch");
    }
    public List<Map<String,Object>> resource(String scenario,String resource) {
        Map<String,List<Map<String,Object>>> available=scenarios.get(scenario);
        if (available==null) throw new IllegalArgumentException("Unknown fixture scenario");
        if (resource==null) {
            if (available.size()!=1) throw new IllegalArgumentException("Explicit resource required");
            return available.values().iterator().next();
        }
        if (!available.containsKey(resource)) throw new IllegalArgumentException("Unknown fixture resource");
        return available.get(resource);
    }
    public Set<String> scenarios() { return Collections.unmodifiableSet(scenarios.keySet()); }
}
