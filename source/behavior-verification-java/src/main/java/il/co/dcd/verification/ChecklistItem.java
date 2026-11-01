package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import java.util.*;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;

/** One syntactic obligation tied to a particular original source revision and body. */
final class ChecklistItem {
    final CodeNode owner;
    final Node site;
    final String id, kind, detail;
    final Map<String, String> properties = new TreeMap<>();
    final List<String> arguments = new ArrayList<>();
    final List<String> candidates = new ArrayList<>();

    ChecklistItem(CodeNode owner, Node site, String kind, String detail) {
        this.owner = owner;
        this.site = site;
        this.kind = kind;
        this.detail = detail;
        var range = site.getRange().orElseThrow();
        String span = range.begin.line + ":" + range.begin.column + ":" + range.end.line + ":" + range.end.column;
        id = "check-" + CodeNode.hash(owner.id + "\0" + kind + "\0" + detail + "\0" + span);
    }

    ChecklistItem property(String key, String value) { properties.put(key, value); return this; }

    void write(XMLStreamWriter output) throws XMLStreamException {
        var range = site.getRange().orElseThrow();
        output.writeStartElement("item");
        output.writeAttribute("id", id);
        output.writeAttribute("code_node_id", owner.id);
        output.writeAttribute("kind", kind);
        output.writeAttribute("detail", detail);
        output.writeAttribute("syntax_type", site.getClass().getSimpleName());
        output.writeAttribute("source_identity", owner.source.getAttribute("identity"));
        output.writeAttribute("source_hash", owner.source.getAttribute("hash"));
        output.writeAttribute("start_line", Integer.toString(range.begin.line));
        output.writeAttribute("end_line", Integer.toString(range.end.line));
        output.writeAttribute("start_column", Integer.toString(range.begin.column));
        output.writeAttribute("end_column", Integer.toString(range.end.column));
        text(output, "excerpt", site.getTokenRange().orElseThrow().toString());
        for (var value : properties.entrySet()) {
            output.writeStartElement("property");
            output.writeAttribute("name", value.getKey());
            // Preserve Java UTF-16 values, including NUL, without invalid XML characters.
            output.writeAttribute("encoding", "utf-16be-base64");
            output.writeCharacters(encoded(value.getValue()));
            output.writeEndElement();
        }
        for (String argument : arguments) text(output, "argument", argument);
        for (String candidate : new TreeSet<>(candidates)) {
            output.writeEmptyElement("candidate"); output.writeAttribute("id", candidate);
        }
        output.writeEndElement();
    }

    private static void text(XMLStreamWriter output, String name, String text) throws XMLStreamException {
        output.writeStartElement(name); output.writeCharacters(text); output.writeEndElement();
    }

    private static String encoded(String text) {
        byte[] units = new byte[text.length() * 2];
        for (int index = 0; index < text.length(); index++) {
            units[index * 2] = (byte) (text.charAt(index) >>> 8);
            units[index * 2 + 1] = (byte) text.charAt(index);
        }
        return Base64.getEncoder().encodeToString(units);
    }
}
