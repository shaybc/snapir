// External launcher settings. This code is never part of the operation or service JAR.
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

final class DemoBinding {
    static final ObjectMapper JSON = new ObjectMapper();
    final JsonNode settings;
    final Path directory, tool, server, driver, catalogue, state;

    DemoBinding(Path binding, boolean validateOperation) throws Exception {
        directory = binding.toAbsolutePath().getParent();
        settings = JSON.readTree(binding.toFile()).path("demo");
        if (!settings.isObject()) throw new IllegalArgumentException("Demo is unavailable; run the converter's demo preparation for this operation");
        tool = resolve("tool_root").toRealPath();
        Path release = tool.resolve("release.json");
        if (!hash(release).equals(text("release_hash"))) throw new IllegalArgumentException("Demo release changed");
        JsonNode manifest = JSON.readTree(release.toFile());
        if (!manifest.path("bundle_id").asText().equals(text("bundle_id")))
            throw new IllegalArgumentException("Demo bundle identity changed");
        Set<Path> expected = new HashSet<>(Set.of(release.toRealPath()));
        var entries = manifest.path("files").fields();
        while (entries.hasNext()) {
            var entry = entries.next();
            Path file = tool.resolve(entry.getKey()).normalize().toRealPath();
            if (!file.startsWith(tool) || !Files.isRegularFile(file) ||
                Files.size(file) != entry.getValue().path("size").asLong() ||
                !hash(file).equals(entry.getValue().path("sha256").asText()))
                throw new IllegalArgumentException("Demo tool file changed");
            expected.add(file);
        }
        try (var files = Files.walk(tool)) {
            for (Path path : files.filter(Files::isRegularFile).toList())
                if (!expected.contains(path.toRealPath())) throw new IllegalArgumentException("Unlisted demo tool file");
        }
        if (!text("driver_jar").equals("jdbc/fixture-jdbc-driver.jar") ||
            !text("server_jar").equals("server/fixture-server.jar") ||
            !text("driver_class").equals(manifest.path("driver_class").asText()))
            throw new IllegalArgumentException("Demo driver or server binding changed");
        driver = tool.resolve(text("driver_jar"));
        server = tool.resolve(text("server_jar"));
        catalogue = resolve("fixture_catalogue");
        // Maven clean removes target before each batch launch. Ownership must survive it.
        state = directory.resolve(".demo-runtime");
        Set<Path> operationFiles=new HashSet<>();
        var sources=(validateOperation ? settings.path("operation_files") : JSON.createObjectNode()).fields();
        while(sources.hasNext()) {
            var entry=sources.next();
            Path source=directory.getParent().resolve(entry.getKey()).normalize().toRealPath();
            if(!source.startsWith(directory.getParent().toRealPath()) || !hash(source).equals(entry.getValue().asText()))
                throw new IllegalArgumentException("Operation changed after demo preparation");
            operationFiles.add(source);
        }
        Path main=directory.getParent().resolve("src/main");
        if(validateOperation && Files.exists(main)) try(var files=Files.walk(main)) {
            for(Path path:files.filter(Files::isRegularFile).toList())
                if(!operationFiles.contains(path.toRealPath())) throw new IllegalArgumentException("Operation has unrecorded files after demo preparation");
        }
        if (!text("jdbc_url").startsWith("jdbc:fixtures:")) throw new IllegalArgumentException("Invalid fixture JDBC scheme");
        java.net.URI url = java.net.URI.create(text("jdbc_url").substring("jdbc:fixtures:".length()));
        if (url.getPort() < 1 ||
            !java.net.InetAddress.getByName(url.getHost()).isLoopbackAddress() || url.getUserInfo() != null)
            throw new IllegalArgumentException("Auto-start requires an explicit local fixture JDBC URL and port");
        if (url.getQuery() != null && url.getQuery().contains("execution="))
            throw new IllegalArgumentException("The launcher owns the per-invocation execution label");
        int startup=settings.path("startup_timeout_ms").asInt(15000);
        int invocation=settings.path("invocation_timeout_ms").asInt(120000);
        if (startup<250 || startup>60000 || invocation<250 || invocation>600000 ||
            !text("database").matches("[A-Za-z0-9_-]+") || !settings.path("fixture_roots").isArray() ||
            settings.path("fixture_roots").isEmpty()) throw new IllegalArgumentException("Invalid bounded demo launch settings");
    }

    String text(String key) {
        String value = settings.path(key).asText();
        if (value.isBlank()) throw new IllegalArgumentException("Missing demo setting: " + key);
        return value;
    }
    Path resolve(String key) { return directory.resolve(text(key)).normalize().toAbsolutePath(); }
    static String hash(Path path) throws Exception {
        try (var input = Files.newInputStream(path)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[65536]; int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer,0,count);
            return HexFormat.of().formatHex(digest.digest());
        }
    }
}
