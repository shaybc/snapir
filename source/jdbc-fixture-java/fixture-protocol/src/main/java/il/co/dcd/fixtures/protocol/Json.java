package il.co.dcd.fixtures.protocol;

import com.fasterxml.jackson.core.StreamReadConstraints;
import com.fasterxml.jackson.databind.*;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;

/** Bounded JSON and Python-compatible canonical hashing for tool manifests. */
public final class Json {
    public static final int MAX_BYTES = 8 * 1024 * 1024;
    public static final ObjectMapper MAPPER = new ObjectMapper()
        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
    static {
        MAPPER.getFactory().setStreamReadConstraints(StreamReadConstraints.builder()
            .maxNestingDepth(100).maxStringLength(MAX_BYTES).maxNumberLength(1000).build());
        MAPPER.enable(com.fasterxml.jackson.core.JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
    }
    private Json() { }
    public static Object read(byte[] bytes) throws IOException {
        if (bytes.length > MAX_BYTES) throw new IOException("JSON byte limit exceeded");
        return MAPPER.readValue(bytes, Object.class);
    }
    @SuppressWarnings("unchecked") public static Map<String,Object> object(Object value) {
        if (!(value instanceof Map<?,?> map) || map.keySet().stream().anyMatch(k -> !(k instanceof String)))
            throw new IllegalArgumentException("Expected JSON object");
        return (Map<String,Object>) map;
    }
    public static byte[] bytes(Object value) throws IOException { return MAPPER.writeValueAsBytes(value); }
    public static String hash(byte[] value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value)); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    public static String digest(Object value) { return hash(canonical(value).getBytes(StandardCharsets.UTF_8)); }
    /** Matches json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=True). */
    public static String canonical(Object value) {
        if (value == null) return "null";
        if (value instanceof String s) {
            StringBuilder out = new StringBuilder("\"");
            for (char c : s.toCharArray()) {
                switch (c) {
                    case '"' -> out.append("\\\""); case '\\' -> out.append("\\\\");
                    case '\b' -> out.append("\\b"); case '\f' -> out.append("\\f");
                    case '\n' -> out.append("\\n"); case '\r' -> out.append("\\r"); case '\t' -> out.append("\\t");
                    default -> { if (c < 32 || c > 126) out.append(String.format("\\u%04x", (int)c)); else out.append(c); }
                }
            }
            return out.append('"').toString();
        }
        if (value instanceof Boolean || value instanceof Number) return value.toString();
        if (value instanceof List<?> list) return "[" + String.join(",", list.stream().map(Json::canonical).toList()) + "]";
        if (value instanceof Map<?,?>) {
            Map<String,Object> map = object(value);
            Comparator<String> unicodeOrder = (a,b) -> Arrays.compare(a.codePoints().toArray(), b.codePoints().toArray());
            return "{" + String.join(",", map.keySet().stream().sorted(unicodeOrder)
                .map(k -> canonical(k) + ":" + canonical(map.get(k))).toList()) + "}";
        }
        throw new IllegalArgumentException("Unsupported JSON value");
    }
    public static void keys(Map<String,Object> value, String... allowed) {
        if (!Set.of(allowed).containsAll(value.keySet())) throw new IllegalArgumentException("Unsupported JSON field");
    }
}
