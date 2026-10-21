package il.co.dcd.composermapper.util;

import java.util.Map;
import java.io.IOException;
import java.io.StringWriter;
import java.io.UncheckedIOException;
import java.io.Writer;

/** Serialize manifest primitives without adding a runtime dependency to the Mapper. */
public final class JsonOutput {
    private JsonOutput() {}
    public static String encode(Object value) {
        StringWriter result = new StringWriter();
        try {
            write(value, result);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return result.toString();
    }

    /** Writes JSON incrementally without collecting serialized children; leaves the writer open. */
    public static void write(Object value, Writer out) throws IOException {
        if (value == null) { out.write("null"); return; }
        if (value instanceof Number || value instanceof Boolean) { out.write(value.toString()); return; }
        if (value instanceof Map<?, ?> map) {
            out.write('{');
            boolean first = true;
            for (var entry : map.entrySet()) {
                if (!first) out.write(',');
                first = false;
                write(entry.getKey().toString(), out);
                out.write(':');
                write(entry.getValue(), out);
            }
            out.write('}');
            return;
        }
        if (value instanceof Iterable<?> items) {
            out.write('[');
            boolean first = true;
            for (var item : items) {
                if (!first) out.write(',');
                first = false;
                write(item, out);
            }
            out.write(']');
            return;
        }
        out.write('"');
        String text = value.toString();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            switch (c) {
                case '"' -> out.write("\\\"");
                case '\\' -> out.write("\\\\");
                case '\n' -> out.write("\\n");
                case '\r' -> out.write("\\r");
                case '\t' -> out.write("\\t");
                default -> { if (c < 32) out.write(String.format("\\u%04x", (int)c)); else out.write(c); }
            }
        }
        out.write('"');
    }
}
