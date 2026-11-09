import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.*;

/** Verify original retained library bytes before and after portable package staging. */
final class PackageRetainedDependencies {
    static void verify(Path project) throws Exception {
        try(var paths=Files.walk(project)) {
            for(Path root:paths.filter(Files::isDirectory)
                    .filter(path->path.getFileName().toString().equals("retained-dependencies")).toList()) {
                JsonNode lock=DemoBinding.JSON.readTree(root.resolve("dependencies.lock.json").toFile());
                if(lock.path("schema_version").asInt()!=1 || !lock.path("files").isObject())
                    throw new IllegalArgumentException("Unsupported retained dependency manifest");
                var files=lock.path("files").fields();
                while(files.hasNext()) {
                    var entry=files.next();
                    Path file=PackageFiles.inside(root,entry.getKey());
                    if(Files.isSymbolicLink(file) || !file.toRealPath().startsWith(root.toRealPath()) ||
                            !DemoBinding.hash(file).equals(entry.getValue().asText()))
                        throw new IllegalArgumentException("Retained dependency changed: "+entry.getKey());
                }
            }
        }
    }
}
