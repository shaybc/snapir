package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.Json;
import java.nio.file.*;
import java.util.*;

/** Test-only publisher; cross-language tests separately use the actual Python publisher. */
final class TestAssets {
    static Path publish(Path root,List<Map<String,Object>> queries) throws Exception {
        Files.createDirectories(root);Path assets=root.resolve("assets");Files.createDirectories(assets);
        Map<String,Object> documents=Map.of("fixtures.json",Map.of("schema_version","shared-fixtures-v1","unresolved",List.of(),"fixtures",
            Map.of("db",Map.of("kind","database","value",Map.of("queries",queries)))),"junit-scenarios.json",Map.of("scenarios",List.of()),"comparison-scenarios.json",Map.of("scenarios",List.of()));
        Map<String,Object> hashes=new TreeMap<>();
        for(var entry : documents.entrySet()) {byte[] bytes=Json.bytes(entry.getValue());Files.write(assets.resolve(entry.getKey()),bytes);hashes.put(entry.getKey(),Json.hash(bytes));}
        Map<String,Object> manifest=Map.of("schema_version","test-assets-v1","boundary_identity","test","revision","r","context_hash","c","files",hashes);
        Files.write(assets.resolve("manifest.json"),Json.bytes(manifest));
        Map<String,Object> catalogue=Map.of("schema_version","fixture-jdbc-catalogue-v1","scenarios",Map.of("success",Map.of("resources",
            Map.of("database",Map.of("fixtures",List.of(Map.of("asset_root","assets","manifest_hash",Json.digest(manifest),"fixture_id","db","pointer","")))))));
        Path path=root.resolve("catalogue.json");Files.write(path,Json.bytes(catalogue));return path;
    }
    static FixtureCatalogue load(Path path) throws Exception {
        return new FixtureCatalogue(path,Json.digest(Json.read(Files.readAllBytes(path))),List.of(path.getParent()));
    }
    static List<Map<String,Object>> queries() {
        return List.of(Map.of("sql","SELECT Value FROM T WHERE Id = ?","parameters",List.of(7),"columns",List.of("Value","Optional"),"rows",List.of(Arrays.asList("שלום\r\n<xml>",null))),
            Map.of("sql","{call TEST(?,?,?)}","parameters",List.of("C"),"out_parameters",Map.of("2",Map.of("sql_type",12,"value","210"),"3",Map.of("sql_type",2012,"columns",List.of("Id"),"rows",List.of(List.of(7))))),
            Map.of("sql","SELECT Failure","parameters",List.of(),"exception",Map.of("type","java.sql.SQLException","message","prepared failure")));
    }
}
