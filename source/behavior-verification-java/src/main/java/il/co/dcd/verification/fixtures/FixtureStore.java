package il.co.dcd.verification.fixtures;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonGenerator;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import il.co.dcd.verification.harness.FixtureInvocation;

/** JUnit reads the same immutable fixture bank as comparison, using independent scenarios. */
public final class FixtureStore {
    private static final ObjectMapper JSON = new ObjectMapper().configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true)
        .configure(JsonGenerator.Feature.ESCAPE_NON_ASCII, true);
    private final Map<String, Object> bank;
    private final Map<String, Object> suite;
    private final String manifestHash;
    private FixtureStore(Map<String, Object> bank, Map<String, Object> suite, String manifestHash) { this.bank = bank; this.suite = suite; this.manifestHash = manifestHash; }

    @SuppressWarnings("unchecked") public static FixtureStore open(String directory, String expectedHash) throws Exception {
        Path root = Path.of(directory).toRealPath();
        Map<String, Object> manifest = JSON.readValue(Files.readAllBytes(root.resolve("manifest.json")), Map.class);
        if (!hash(JSON.writeValueAsBytes(manifest)).equals(expectedHash)) throw new IllegalArgumentException("Fixture manifest changed");
        Map<String, String> files = (Map<String, String>) manifest.get("files");
        if (!files.keySet().containsAll(Set.of("fixtures.json", "junit-scenarios.json", "comparison-scenarios.json"))
            || !Set.of("fixtures.json", "junit-scenarios.json", "comparison-scenarios.json", "validation.json").containsAll(files.keySet())) throw new IllegalArgumentException("Unexpected asset files");
        for (var entry : files.entrySet()) {
            Path path = root.resolve(entry.getKey()).toRealPath();
            if (!path.getParent().equals(root) || !hash(Files.readAllBytes(path)).equals(entry.getValue())) throw new IllegalArgumentException("Fixture document changed");
        }
        return new FixtureStore(JSON.readValue(Files.readAllBytes(root.resolve("fixtures.json")), Map.class),
            JSON.readValue(Files.readAllBytes(root.resolve("junit-scenarios.json")), Map.class), expectedHash);
    }
    public static String hash(byte[] data) throws Exception { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data)); }

    @SuppressWarnings("unchecked") public FixtureResult run(String scenarioId) throws Exception {
        // Deserialize fresh maps and lists even if the same FixtureStore instance is reused.
        Map<String, Object> scenario = null;
        for (Map<String, Object> item : (List<Map<String, Object>>) suite.get("scenarios")) if (scenarioId.equals(item.get("scenario_id"))) scenario = item;
        if (scenario == null) throw new IllegalArgumentException("Missing JUnit scenario: " + scenarioId);
        if (!((List<?>) suite.getOrDefault("unresolved", List.of())).isEmpty() || !((List<?>) bank.getOrDefault("unresolved", List.of())).isEmpty()
            || !((List<?>) scenario.getOrDefault("unresolved", List.of())).isEmpty()) throw new IllegalArgumentException("JUnit scenario has unresolved inputs");
        Map<String, Object> inputs = new LinkedHashMap<>(), resources = new LinkedHashMap<>(), configuration = new LinkedHashMap<>();
        for (var entry : ((Map<String, Object>) scenario.get("inputs")).entrySet()) inputs.put(entry.getKey(), reference((Map<String, Object>) entry.getValue(), new HashSet<>()));
        for (var entry : ((Map<String, Object>) scenario.get("resources")).entrySet()) resources.put(entry.getKey(), reference((Map<String, Object>) entry.getValue(), new HashSet<>()));
        for (var entry : ((Map<String, Object>) scenario.getOrDefault("configuration",Map.of())).entrySet()) configuration.put(entry.getKey(),reference((Map<String,Object>)entry.getValue(),new HashSet<>()));
        Object xml = scenario.get("input_xml") == null ? null : reference((Map<String, Object>) scenario.get("input_xml"), new HashSet<>());
        FixtureResources.reset(Map.of("inputs", inputs, "resources", resources));
        try {
            FixtureResult result;
            try(var setup=il.co.dcd.verification.harness.FixtureStaticConfiguration.open((List<Map<String,Object>>)scenario.getOrDefault("setup",List.of()),(String)xml,FixtureResources.inputs(),configuration)) {
                result = FixtureInvocation.run((Map<String, Object>) scenario.get("native_entry"), (String) xml, FixtureResources.inputs(), configuration,
                    scenario.getOrDefault("entry_kind","method").equals("constructor"));
                FixtureResources.verify();
            }
            receipt(scenarioId); return result;
        }
        finally { FixtureResources.clear(); }
    }
    private void receipt(String id) throws Exception {
        List<String> callers = StackWalker.getInstance().walk(frames -> frames.limit(64)
            .map(frame -> frame.getClassName()+"#"+frame.getMethodName()).toList());
        byte[] line = (JSON.writeValueAsString(Map.of("scenario_id",id,"manifest_hash",manifestHash,"callers",callers))+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
        Path path = Path.of("target", "shared-fixture-executions.jsonl"); Files.createDirectories(path.getParent());
        synchronized (FixtureStore.class) {
            try (var channel = java.nio.channels.FileChannel.open(path,StandardOpenOption.CREATE,StandardOpenOption.WRITE,StandardOpenOption.APPEND);
                    var lock = channel.lock()) { channel.write(java.nio.ByteBuffer.wrap(line)); }
        }
    }
    @SuppressWarnings("unchecked") private Object reference(Map<String, Object> ref, Set<String> active) {
        String id = (String) ref.get("fixture_id");
        if (!active.add(id)) throw new IllegalArgumentException("Cyclic fixture reference");
        Map<String, Object> fixtures = (Map<String, Object>) bank.get("fixtures");
        if (!fixtures.containsKey(id)) throw new IllegalArgumentException("Missing fixture: " + id);
        Object value = expand(((Map<String, Object>) fixtures.get(id)).get("value"), active);
        active.remove(id);
        return FixtureResources.pointer(value, (String) ref.getOrDefault("pointer", ""));
    }
    @SuppressWarnings("unchecked") private Object expand(Object value, Set<String> active) {
        if (value instanceof Map<?, ?> map) {
            if (map.containsKey("$fixture")) {
                if (!Set.of("$fixture", "pointer").containsAll(map.keySet())) throw new IllegalArgumentException("Malformed fixture reference");
                return reference(Map.of("fixture_id", map.get("$fixture"), "pointer", map.containsKey("pointer") ? map.get("pointer") : ""), active);
            }
            Map<String, Object> result = new LinkedHashMap<>(); map.forEach((key, child) -> result.put((String) key, expand(child, active))); return result;
        }
        if (value instanceof List<?> list) return list.stream().map(child -> expand(child, active)).collect(java.util.stream.Collectors.toCollection(ArrayList::new));
        return value;
    }
}
