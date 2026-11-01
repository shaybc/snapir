package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** One original executable body or Java-defined implicit initialization step. */
final class CodeNode {
    final String id, owner, signature, kind;
    final Node anchor, body;
    final Element source;

    CodeNode(SourceScope scope, Node anchor, Node body, String owner, String signature, String kind) {
        this.anchor = anchor;
        this.body = body;
        this.owner = owner;
        this.signature = signature;
        this.kind = kind;
        source = scope.evidence(anchor.findCompilationUnit().orElseThrow());
        var range = anchor.getRange().orElseThrow();
        id = "code-" + hash(source.getAttribute("identity") + "\0" + source.getAttribute("hash") + "\0" + kind + "\0" + range);
    }

    static String hash(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException exception) { throw new IllegalStateException(exception); }
    }

    void write(XMLStreamWriter output) throws XMLStreamException {
        var range = anchor.getRange().orElseThrow();
        output.writeStartElement("code");
        output.writeAttribute("id", id);
        output.writeAttribute("kind", kind);
        output.writeAttribute("declaring_class", owner);
        output.writeAttribute("signature", signature);
        if (kind.endsWith("_field_default")) {
            var type = ((com.github.javaparser.ast.body.VariableDeclarator) anchor).getType();
            String value = !type.isPrimitiveType() ? "null" : switch (type.asString()) {
                case "boolean" -> "false";
                case "char" -> "\\u0000";
                case "float", "double" -> "0.0";
                default -> "0";
            };
            output.writeAttribute("initialization_rule", "java_default_value");
            output.writeAttribute("default_value", value);
        }
        output.writeAttribute("source_identity", source.getAttribute("identity"));
        output.writeAttribute("source_hash", source.getAttribute("hash"));
        output.writeAttribute("start_line", Integer.toString(range.begin.line));
        output.writeAttribute("end_line", Integer.toString(range.end.line));
        output.writeAttribute("start_column", Integer.toString(range.begin.column));
        output.writeAttribute("end_column", Integer.toString(range.end.column));
        output.writeStartElement("excerpt");
        output.writeCharacters(anchor.getTokenRange().orElseThrow().toString());
        output.writeEndElement();
        output.writeEndElement();
    }
}
