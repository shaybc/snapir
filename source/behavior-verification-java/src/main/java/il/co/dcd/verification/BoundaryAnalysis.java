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
        AnalysisProgress.report("reading input manifest");
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element input = factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        try (var stream = Files.newOutputStream(Path.of(args[1]))) {
            XMLStreamWriter output = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
            output.writeStartDocument();
            output.writeStartElement("analysis");
            output.writeAttribute("classpath_protocol", "project-classpath-v1");
            for (Node node = input.getFirstChild(); node != null; node = node.getNextSibling()) {
                if (!(node instanceof Element scope) || !scope.getTagName().equals("scope")) continue;
                AnalysisProgress.report("scope " + scope.getAttribute("id") + " preparing sources and classpath");
                try (SourceScope sources = new SourceScope(scope)) {
                    AnalysisProgress.report("scope ready " + scope.getAttribute("id"));
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
            AnalysisProgress.report("entry " + entry.getAttribute("id") + " resolving " + entry.getAttribute("implementation") + "." + entry.getAttribute("method"));
            output.writeStartElement("entry");
            output.writeAttribute("id", entry.getAttribute("id"));
            try {
                if (problem != null) throw new IllegalStateException(problem);
                EntryMethod.write(entry, sources, output);
                if (entry.getAttribute("reachability").equals("true")) {
                    AnalysisProgress.report("entry " + entry.getAttribute("id") + " indexing source catalog");
                    ReachableSlice graph = new ReachableSlice(new SourceCatalog(sources));
                    AnalysisProgress.report("entry " + entry.getAttribute("id") + " traversing reachable calls");
                    try { graph.analyze(entry); }
                    catch (RuntimeException exception) { graph.issues.add("Reachability did not finish: " + exception.getClass().getSimpleName() + ": " + exception.getMessage()); }
                    graph.write(output);
                    if (!entry.getAttribute("checklist").equals("false")) {
                        AnalysisProgress.report("entry " + entry.getAttribute("id") + " extracting parser checklist");
                        ParserChecklist checklist = new ParserChecklist(graph);
                        checklist.analyze();
                        checklist.write(output);
                        AnalysisProgress.report("entry " + entry.getAttribute("id") + " extracting basic checklist");
                        ParserChecklist basicChecklist = new ParserChecklist(graph, true);
                        basicChecklist.analyze();
                        basicChecklist.write(output);
                    }
                }
            } catch (RuntimeException exception) {
                output.writeEmptyElement("issue");
                output.writeAttribute("message", exception.getMessage() == null ? exception.getClass().getSimpleName() : exception.getMessage());
            }
            output.writeEndElement();
            AnalysisProgress.report("entry complete " + entry.getAttribute("id"));
        }
    }
}
