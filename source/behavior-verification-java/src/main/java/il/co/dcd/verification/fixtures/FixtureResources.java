package il.co.dcd.verification.fixtures;

import java.util.*;
import il.co.dcd.verification.harness.BoundaryRuntime;

/** Fresh scenario-local resources; no network or real JDBC connection is constructed. */
public final class FixtureResources {
    private static final ThreadLocal<Map<String, Object>> inputs = ThreadLocal.withInitial(Map::of);
    private static final ThreadLocal<Map<String, Object>> resources = ThreadLocal.withInitial(Map::of);
    private static final ThreadLocal<List<Map<String, Object>>> events = ThreadLocal.withInitial(ArrayList::new);
    private static final ThreadLocal<List<String>> incomplete = ThreadLocal.withInitial(ArrayList::new);
    private FixtureResources() { }

    @SuppressWarnings("unchecked") public static void reset(Map<String, Object> assets) {
        incomplete.set(new ArrayList<>());
        inputs.set((Map<String, Object>) normalize(assets.getOrDefault("inputs", Map.of())));
        events.set(new ArrayList<>());
        Map<String, Object> result = new LinkedHashMap<>();
        for (var item : ((Map<String, Object>) assets.getOrDefault("resources", Map.of())).entrySet()) {
            if (!(item.getValue() instanceof Map<?, ?> spec) || !spec.containsKey("queries"))
                throw new BoundaryRuntime.Incomplete("Unsupported fixture resource provider: " + item.getKey());
            result.put(item.getKey(), JdbcFixtureProvider.connection((Map<String, Object>) normalize(spec), events.get(), item.getKey()));
        }
        resources.set(result);
    }
    public static Object input(String key) {
        if (!inputs.get().containsKey(key)) throw new BoundaryRuntime.Incomplete("Missing fixture input: " + key);
        return inputs.get().get(key);
    }
    public static Object resource(String key) {
        if (!resources.get().containsKey(key)) throw new BoundaryRuntime.Incomplete("Missing fixture resource: " + key);
        return resources.get().get(key);
    }
    public static List<Map<String, Object>> events() { return new ArrayList<>(events.get()); }
    public static Map<String,Object> inputs() { return inputs.get(); }
    public static void incomplete(String message) { incomplete.get().add(message); }
    public static void verify() {
        if (!incomplete.get().isEmpty()) throw new BoundaryRuntime.Incomplete("Fixture capability failure was caught by tested code: "+incomplete.get().get(0));
    }
    public static void clear() { inputs.remove(); resources.remove(); events.remove(); incomplete.remove(); }
    private static Object normalize(Object value) {
        if (value instanceof Map<?,?> map) {
            if (map.size()==1 && map.containsKey("$decimal")) return new java.math.BigDecimal(map.get("$decimal").toString());
            if (map.size()==1 && map.containsKey("$date_millis")) return new Date(((Number)map.get("$date_millis")).longValue());
            Map<String,Object> result=new LinkedHashMap<>();map.forEach((key,child)->result.put((String)key,normalize(child)));return result;
        }
        if (value instanceof List<?> list) return list.stream().map(FixtureResources::normalize).collect(java.util.stream.Collectors.toCollection(ArrayList::new));
        return value;
    }
    public static <T> T checked(T receiver) {
        if (!JdbcFixtureProvider.owned(receiver)) throw new BoundaryRuntime.Incomplete("JDBC receiver is not a fixture-backed resource");
        return receiver;
    }
    public static Object pointer(Object value, String path) {
        if (path.isEmpty()) return value;
        if (!path.startsWith("/") || path.matches(".*~(?![01]).*")) throw new BoundaryRuntime.Incomplete("Invalid fixture pointer");
        for (String raw : path.substring(1).split("/", -1)) {
            String token = raw.replace("~1", "/").replace("~0", "~");
            if (value instanceof Map<?, ?> map && map.containsKey(token)) value = map.get(token);
            else if (value instanceof List<?> list && token.matches("0|[1-9][0-9]*") && Long.parseLong(token) < list.size()) value = list.get(Integer.parseInt(token));
            else throw new BoundaryRuntime.Incomplete("Missing fixture pointer: " + path);
        }
        return value;
    }
}
