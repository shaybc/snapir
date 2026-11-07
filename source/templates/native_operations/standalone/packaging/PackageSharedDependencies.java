import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.*;
import java.util.*;

/** Verify portable generated libraries against their immutable component manifests. */
final class PackageSharedDependencies {
    static void verify(Path repository) throws Exception {
        try(var paths=Files.walk(repository)) {
            for(Path root:paths.filter(Files::isDirectory)
                    .filter(path->path.getFileName().toString().equals("shared-dependencies")).toList())verifyStore(root);
        }
    }
    static void verifyStore(Path root) throws Exception {
        JsonNode lock=DemoBinding.JSON.readTree(root.resolve("dependencies.lock.json").toFile());
        if(lock.path("schema_version").asInt()!=1)throw new IllegalArgumentException("Unsupported component dependency lock");
        for(JsonNode component:lock.path("components")) {
            String revision=component.path("revision").asText();
            if(!revision.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Invalid component revision");
            Path directory=PackageFiles.inside(root,"components/"+revision);
            JsonNode manifest=DemoBinding.JSON.readTree(directory.resolve("manifest.json").toFile());
            if(!revision.equals(manifest.path("revision").asText()) || !manifest.path("status").asText().equals("approved"))
                throw new IllegalArgumentException("Incomplete shared component publication");
            var entries=manifest.path("files").fields();
            while(entries.hasNext()) {
                var entry=entries.next();
                Path source=PackageFiles.inside(directory,entry.getKey());
                if(Files.isSymbolicLink(source) || !source.toRealPath().startsWith(directory.toRealPath()) ||
                        !DemoBinding.hash(source).equals(entry.getValue().asText()))
                    throw new IllegalArgumentException("Shared component artifact changed");
            }
            JsonNode metadata=manifest.path("metadata"), coordinates=metadata.path("coordinates");
            String artifact=coordinates.path("artifact_id").asText(), version=coordinates.path("version").asText();
            String prefix=coordinates.path("group_id").asText().replace('.','/')+"/"+artifact+"/"+version+"/"+artifact+"-"+version;
            for(String suffix:List.of("jar","pom")) {
                Path published=PackageFiles.inside(directory,metadata.path(suffix).asText());
                Path local=PackageFiles.inside(root,"repository/"+prefix+"."+suffix);
                if(!DemoBinding.hash(published).equals(DemoBinding.hash(local)))
                    throw new IllegalArgumentException("Portable generated Maven dependency changed");
            }
        }
    }
}
