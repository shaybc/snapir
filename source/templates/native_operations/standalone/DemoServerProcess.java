// Use the prebuilt lifecycle CLI; do not implement a second server or SQL matcher.
import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

final class DemoServerProcess {
    static String javaCommand() {
        return Path.of(System.getProperty("java.home"),"bin",
            System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java").toString();
    }
    static JsonNode command(DemoBinding binding, String action, String... extra) throws Exception {
        List<String> args = new ArrayList<>(List.of(javaCommand(),"-jar",binding.server.toString(),action,
            "--state-dir",binding.state.toString()));
        if (action.equals("ensure")) {
            args.addAll(List.of("--jdbc-url",binding.text("jdbc_url"),"--catalogue",binding.catalogue.toString(),
                "--expected-hash",binding.text("catalogue_hash"),"--startup-timeout-ms",
                String.valueOf(binding.settings.path("startup_timeout_ms").asInt(15000))));
            for (JsonNode root : binding.settings.path("fixture_roots"))
                args.addAll(List.of("--fixture-root",binding.directory.resolve(root.asText()).normalize().toString()));
        }
        args.addAll(Arrays.asList(extra));
        Files.createDirectories(binding.state);
        Path out = Files.createTempFile(binding.state,".command-",".json");
        Path err = Files.createTempFile(binding.state,".command-",".log");
        Process process = null;
        try {
            process = new ProcessBuilder(args).redirectOutput(out.toFile()).redirectError(err.toFile()).start();
            if (!process.waitFor(30,TimeUnit.SECONDS)) throw new IllegalStateException("Fixture lifecycle command timed out");
            if (process.exitValue()!=0) {
                if (Files.size(err)<=8192) System.err.print(Files.readString(err));
                throw new IllegalStateException("Fixture lifecycle command failed; inspect server.log and fixture identities");
            }
            if (Files.size(out)>8*1024*1024) throw new IllegalStateException("Fixture lifecycle response exceeded limit");
            return DemoBinding.JSON.readTree(out.toFile());
        } finally {
            if (process!=null && process.isAlive()) { process.destroyForcibly(); process.waitFor(5,TimeUnit.SECONDS); }
            Files.deleteIfExists(out); Files.deleteIfExists(err);
        }
    }
}
