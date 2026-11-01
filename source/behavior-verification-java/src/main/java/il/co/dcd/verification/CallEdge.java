package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import java.util.List;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;

/** A source call site and its full supplied-evidence candidate list, including uncertainty. */
final class CallEdge {
    final String from, kind, declaredTarget, reason;
    final List<String> candidates;
    final boolean uncertain, unbounded;
    final Node site;

    CallEdge(String from, String kind, String declaredTarget, List<String> candidates,
             boolean uncertain, boolean unbounded, String reason, Node site) {
        this.from = from;
        this.kind = kind;
        this.declaredTarget = declaredTarget;
        this.candidates = candidates.stream().distinct().sorted().toList();
        this.uncertain = uncertain;
        this.unbounded = unbounded;
        this.reason = reason;
        this.site = site;
    }

    void write(SourceScope scope, XMLStreamWriter output) throws XMLStreamException {
        output.writeStartElement("edge");
        output.writeAttribute("from_id", from);
        output.writeAttribute("kind", kind);
        output.writeAttribute("declared_target", declaredTarget);
        output.writeAttribute("uncertain", Boolean.toString(uncertain));
        output.writeAttribute("unbounded", Boolean.toString(unbounded));
        output.writeAttribute("reason", reason);
        String location = "configuration";
        if (site != null) {
            var source = scope.evidence(site.findCompilationUnit().orElseThrow());
            var range = site.getRange().orElseThrow();
            location = source.getAttribute("identity") + ":" + range;
            output.writeAttribute("source_identity", source.getAttribute("identity"));
            output.writeAttribute("source_hash", source.getAttribute("hash"));
            output.writeAttribute("start_line", Integer.toString(range.begin.line));
            output.writeAttribute("end_line", Integer.toString(range.end.line));
            output.writeAttribute("start_column", Integer.toString(range.begin.column));
            output.writeAttribute("end_column", Integer.toString(range.end.column));
        }
        output.writeAttribute("id", "edge-" + CodeNode.hash(from + "\0" + kind + "\0" + declaredTarget + "\0" + location + "\0" + candidates));
        if (site != null) {
            output.writeStartElement("excerpt");
            output.writeCharacters(site.getTokenRange().orElseThrow().toString());
            output.writeEndElement();
        }
        for (String candidate : candidates) {
            output.writeEmptyElement("candidate");
            output.writeAttribute("id", candidate);
        }
        output.writeEndElement();
    }
}
