import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import java.net.URLClassLoader;
import java.nio.file.*;
import java.util.*;

/** Rebase validated fixture references into a package, preserving original tool and bank bytes. */
final class PackageDemoAssets {
    static ObjectNode stage(Path project,Path output,ObjectNode binding) throws Exception {
        DemoBinding original=new DemoBinding(project.resolve("standalone/operation.json"),true);
        ObjectNode demo=(ObjectNode)binding.get("demo");
        List<Path> roots=new ArrayList<>();
        for(JsonNode root:original.settings.path("fixture_roots"))roots.add(original.directory.resolve(root.asText()).normalize());
        try(var loader=new URLClassLoader(new java.net.URL[]{original.server.toUri().toURL()},ClassLoader.getPlatformClassLoader())) {
            verify(loader,original.catalogue,original.text("catalogue_hash"),roots);
            Path tool=output.resolve("demo/tools").resolve(original.text("bundle_id"));
            PackageFiles.tree(original.tool,tool);
            Path catalogue=output.resolve("demo/catalogue.json");
            ObjectNode document=(ObjectNode)DemoBinding.JSON.readTree(original.catalogue.toFile());
            Set<Path> copied=new LinkedHashSet<>();
            for(JsonNode scenario:document.path("scenarios"))for(JsonNode resource:scenario.path("resources"))for(JsonNode raw:resource.path("fixtures")) {
                ObjectNode reference=(ObjectNode)raw;
                Path source=original.catalogue.getParent().resolve(reference.path("asset_root").asText()).normalize().toRealPath();
                String identity=reference.path("manifest_hash").asText();
                if(!identity.matches("[a-f0-9]{64}"))throw new IllegalArgumentException("Invalid fixture revision identity");
                Path destination=output.resolve("demo/fixtures").resolve(identity);
                JsonNode manifest=DemoBinding.JSON.readTree(source.resolve("manifest.json").toFile());
                PackageFiles.copy(source.resolve("manifest.json"),destination.resolve("manifest.json"));
                var files=manifest.path("files").fields();
                while(files.hasNext()) {
                    var file=files.next();
                    PackageFiles.copy(PackageFiles.inside(source,file.getKey()),PackageFiles.inside(destination,file.getKey()));
                }
                copied.add(destination);
                reference.put("asset_root",PackageFiles.relative(catalogue.getParent(),destination));
            }
            DemoBinding.JSON.writerWithDefaultPrettyPrinter().writeValue(catalogue.toFile(),document);
            // Use the pinned tooling's canonical identity function instead of a second JSON hashing scheme.
            String hash=(String)loader.loadClass("il.co.dcd.fixtures.protocol.Json").getMethod("digest",Object.class)
                .invoke(null,DemoBinding.JSON.convertValue(document,Object.class));
            verify(loader,catalogue,hash,new ArrayList<>(copied));
            Path settings=output.resolve("standalone");
            demo.put("tool_root",PackageFiles.relative(settings,tool));
            demo.put("fixture_catalogue",PackageFiles.relative(settings,catalogue));
            demo.put("catalogue_hash",hash);
            ArrayNode fixtureRoots=demo.putArray("fixture_roots");
            for(Path path:copied)fixtureRoots.add(PackageFiles.relative(settings,path));
            return demo;
        }
    }
    static void verify(ClassLoader loader,Path catalogue,String hash,List<Path> roots) throws Exception {
        loader.loadClass("il.co.dcd.fixtures.server.FixtureCatalogue").getConstructor(Path.class,String.class,List.class)
            .newInstance(catalogue,hash,roots);
    }
}
