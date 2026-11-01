package il.co.dcd.verification.harness;

import java.math.BigDecimal;
import java.util.*;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** Lossless supported values only: unknown objects never silently become toString results. */
public final class BoundaryValues {
    private BoundaryValues() { }

    public static List<Element> children(Element parent, String name) {
        List<Element> result = new ArrayList<>();
        for (var node = parent.getFirstChild(); node != null; node = node.getNextSibling())
            if (node instanceof Element element && (name == null || element.getTagName().equals(name))) result.add(element);
        return result;
    }

    public static Element child(Element parent, String name) {
        return children(parent, name).stream().findFirst().orElseThrow(() -> new IllegalArgumentException("Missing protocol element " + name));
    }

    public static Object read(Element element) {
        String text = element.getTextContent();
        return switch (element.getAttribute("type")) {
            case "null" -> null;
            case "string" -> {
                byte[] bytes = Base64.getDecoder().decode(text);
                if (bytes.length % 2 != 0) throw new IllegalArgumentException("Invalid UTF-16 units");
                char[] units = new char[bytes.length / 2];
                for (int index = 0; index < units.length; index++) units[index] = (char) ((bytes[index * 2] & 255) << 8 | bytes[index * 2 + 1] & 255);
                yield new String(units);
            }
            case "boolean" -> Boolean.valueOf(text);
            case "number" -> new BigDecimal(text);
            case "date" -> new Date(Long.parseLong(text));
            case "list" -> children(element, "value").stream().map(BoundaryValues::read).toList();
            case "map" -> {
                Map<String, Object> result = new LinkedHashMap<>();
                for (Element entry : children(element, "entry")) {
                    String key = entry.getAttribute("key");
                    if (result.containsKey(key)) throw new IllegalArgumentException("Duplicate boundary key");
                    result.put(key, read(child(entry, "value")));
                }
                yield result;
            }
            default -> throw new IllegalArgumentException("Unsupported boundary protocol type");
        };
    }

    public static Object snapshot(Object value) {
        if (value == null || value instanceof String || value instanceof Boolean || value instanceof Number) return value;
        if (value instanceof Character character) return String.valueOf(character);
        if (value instanceof Enum<?> constant) return Map.of("$enum_type", constant.getDeclaringClass().getName(), "name", constant.name());
        if (value instanceof java.util.logging.Level level) return Map.of("$logging_level", level.getName(), "value", level.intValue());
        if (value instanceof Date date) return new Date(date.getTime());
        if (value instanceof Throwable failure) return Map.of("exception_type", failure.getClass().getName(), "message", String.valueOf(failure.getMessage()));
        if (value.getClass().isArray()) {
            List<Object> result = new ArrayList<>();
            for (int index = 0; index < java.lang.reflect.Array.getLength(value); index++) result.add(snapshot(java.lang.reflect.Array.get(value, index)));
            return result;
        }
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            for (var entry : map.entrySet()) {
                if (!(entry.getKey() instanceof String key)) throw new BoundaryRuntime.Incomplete("Non-string context key");
                result.put(key, snapshot(entry.getValue()));
            }
            return result;
        }
        if (value instanceof Collection<?> collection) return collection.stream().map(BoundaryValues::snapshot).toList();
        throw new BoundaryRuntime.Incomplete("Unsupported observable type: " + value.getClass().getName());
    }

    public static Object comparable(Object value) {
        if (value instanceof Number number) return new Numeric(number.toString());
        if (value instanceof Collection<?> collection) return collection.stream().map(BoundaryValues::comparable).toList();
        if (value instanceof Map<?, ?> map) {
            Map<Object, Object> result = new LinkedHashMap<>(); map.forEach((key, item) -> result.put(key, comparable(item))); return result;
        }
        return value;
    }
    private record Numeric(String text) { }

    public static void write(XMLStreamWriter output, String name, Object original) throws Exception {
        Object value = snapshot(original);
        output.writeStartElement(name);
        if (value == null) output.writeAttribute("type", "null");
        else if (value instanceof String text) {
            output.writeAttribute("type", "string");
            byte[] bytes = new byte[text.length() * 2];
            for (int i = 0; i < text.length(); i++) { bytes[i * 2] = (byte) (text.charAt(i) >>> 8); bytes[i * 2 + 1] = (byte) text.charAt(i); }
            output.writeCharacters(Base64.getEncoder().encodeToString(bytes));
        } else if (value instanceof Boolean || value instanceof Number || value instanceof Date) {
            output.writeAttribute("type", value instanceof Date ? "date" : value instanceof Boolean ? "boolean" : "number");
            output.writeCharacters(value instanceof Date date ? Long.toString(date.getTime()) : value.toString());
        } else if (value instanceof Map<?, ?> map) {
            output.writeAttribute("type", "map");
            for (var entry : map.entrySet()) {
                output.writeStartElement("entry"); output.writeAttribute("key", (String) entry.getKey());
                write(output, "value", entry.getValue()); output.writeEndElement();
            }
        } else if (value instanceof Collection<?> collection) {
            output.writeAttribute("type", "list");
            for (Object item : collection) write(output, "value", item);
        }
        output.writeEndElement();
    }
}
