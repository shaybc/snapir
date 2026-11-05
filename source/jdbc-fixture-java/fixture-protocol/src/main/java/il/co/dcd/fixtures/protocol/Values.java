package il.co.dcd.fixtures.protocol;

import java.math.BigDecimal;
import java.util.*;

/** Explicit type tags preserve JDBC decimal, binary and temporal values over JSON. */
public final class Values {
    private Values() { }
    public static Object encode(Object value) {
        if (value instanceof BigDecimal d) return Map.of("$decimal",d.toPlainString());
        if (value instanceof java.sql.Timestamp d) return Map.of("$timestamp",d.toString());
        if (value instanceof java.sql.Date d) return Map.of("$sql_date",d.toString());
        if (value instanceof java.sql.Time d) return Map.of("$sql_time",d.toString());
        if (value instanceof Date d) return Map.of("$date_millis",d.getTime());
        if (value instanceof byte[] b) return Map.of("$binary",Base64.getEncoder().encodeToString(b));
        if (value instanceof Map<?,?> map) {
            Map<String,Object> out = new LinkedHashMap<>();
            map.forEach((k,v) -> out.put((String)k,encode(v))); return out;
        }
        if (value instanceof List<?> list) return list.stream().map(Values::encode).toList();
        if (value == null || value instanceof String || value instanceof Boolean || value instanceof Number) return value;
        throw new IllegalArgumentException("Unsupported JDBC value type");
    }
    public static Object decode(Object value) {
        if (value instanceof Map<?,?> map) {
            if (map.size()==1) {
                if (map.containsKey("$decimal")) return new BigDecimal(map.get("$decimal").toString());
                if (map.containsKey("$date_millis")) return new Date(((Number)map.get("$date_millis")).longValue());
                if (map.containsKey("$sql_date")) return java.sql.Date.valueOf(map.get("$sql_date").toString());
                if (map.containsKey("$sql_time")) return java.sql.Time.valueOf(map.get("$sql_time").toString());
                if (map.containsKey("$timestamp")) return java.sql.Timestamp.valueOf(map.get("$timestamp").toString());
                if (map.containsKey("$binary")) return Base64.getDecoder().decode(map.get("$binary").toString());
            }
            Map<String,Object> out = new LinkedHashMap<>();
            map.forEach((k,v) -> out.put((String)k,decode(v))); return out;
        }
        if (value instanceof List<?> list) return list.stream().map(Values::decode).toList();
        return value;
    }
}
