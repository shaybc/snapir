package il.co.dcd.verification;

import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.stream.XMLOutputFactory;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/** Locate entry methods without running workspace code; the tool supports Java 21 and 25. */
public final class BoundaryAnalysis {
    private BoundaryAnalysis() { }

    public static void main(String[] args) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element input = factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        try (var stream = Files.newOutputStream(Path.of(args[1]))) {
            XMLStreamWriter output = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
            output.writeStartDocument();
            output.writeStartElement("analysis");
            for (Node node = input.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (!(node instanceof Element scope) || !scope.getTagName().equals("scope")) continue;
                try (SourceScope sources = new SourceScope(scope)) {
                    entries(scope, sources, output, null);
                } catch (RuntimeException exception) {
                    entries(scope, null, output, "Source scope could not be analyzed: " + exception.getMessage());
                }
            }
            output.writeEndElement();
            output.writeEndDocument();
            output.close();
        }
    }

    private static void entries(Element scope, SourceScope sources, XMLStreamWriter output, String problem) throws Exception {
        for (Node node = scope.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (!(node instanceof Element entry) || !entry.getTagName().equals("entry")) continue;
            output.writeStartElement("entry");
            output.writeAttribute("id", entry.getAttribute("id"));
            try {
                if (problem != null) throw new IllegalStateException(problem);
                EntryMethod.write(entry, sources, output);
                if (entry.getAttribute("reachability").equals("true")) {
                    ReachableSlice graph = new ReachableSlice(new SourceCatalog(sources));
                    try { graph.analyze(entry); }
                    catch (RuntimeException exception) { graph.issues.add("Reachability did not finish: " + exception.getClass().getSimpleName() + ": " + exception.getMessage()); }
                    graph.write(output);
                    ParserChecklist checklist = new ParserChecklist(graph);
                    checklist.analyze();
                    checklist.write(output);
                }
            } catch (RuntimeException exception) {
                output.writeEmptyElement("issue");
                output.writeAttribute("message", exception.getMessage() == null ? exception.getClass().getSimpleName() : exception.getMessage());
            }
            output.writeEndElement();
        }
    }
}
