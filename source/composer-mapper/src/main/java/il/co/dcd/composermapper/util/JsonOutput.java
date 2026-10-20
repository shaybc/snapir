package il.co.dcd.composermapper.util;

import java.util.Map;

/** Serialize manifest primitives without adding a runtime dependency to the Mapper. */
public final class JsonOutput {
    private JsonOutput() {}
    public static String encode(Object value) {
        if (value == null) return "null";
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?, ?> map) return "{" + String.join(",", map.entrySet().stream()
            .map(e -> encode(e.getKey().toString()) + ":" + encode(e.getValue())).toList()) + "}";
        if (value instanceof Iterable<?> items) {
            var values = new java.util.ArrayList<String>();
            items.forEach(item -> values.add(encode(item)));
            return "[" + String.join(",", values) + "]";
        }
        StringBuilder result = new StringBuilder("\"");
        for (char c : value.toString().toCharArray()) {
            switch (c) {
                case '"' -> result.append("\\\"");
                case '\\' -> result.append("\\\\");
                case '\n' -> result.append("\\n");
                case '\r' -> result.append("\\r");
                case '\t' -> result.append("\\t");
                default -> { if (c < 32) result.append(String.format("\\u%04x", (int)c)); else result.append(c); }
            }
        }
        return result.append('"').toString();
    }
}
