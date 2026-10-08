package il.co.dcd.composermapper.util;

import java.nio.file.Path;
import java.util.*;

public class Args {
    private final Map<String,String> values = new HashMap<>();

    public static Args parse(String[] args) {
        Args a = new Args();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--")) {
                String k = args[i].substring(2);
                String v = (i + 1 < args.length && !args[i + 1].startsWith("--"))
                    ? args[++i] : "true";
                a.values.put(k, v);
            }
        }
        return a;
    }

    public Path requiredPath(String key) {
        String v = values.get(key);
        if (v == null || v.isBlank()) throw new IllegalArgumentException("Missing --" + key);
        return Path.of(v).toAbsolutePath().normalize();
    }

    public boolean flag(String key, boolean defaultValue) {
        String v = values.get(key);
        return v == null ? defaultValue : Boolean.parseBoolean(v);
    }

    /** Returns the value for key, or null if not provided. */
    public String optional(String key) {
        return values.get(key);
    }
}
