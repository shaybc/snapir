package il.co.dcd.javaanalysis;

import java.nio.file.*;
import java.util.*;
import javax.xml.parsers.*;
import javax.xml.stream.*;

/** Compatibility XML protocol, backed by the exact same analyzer embedded in Mapper. */
public final class ReferenceScanMain {
    public static void main(String[] args) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        var nodes = factory.newDocumentBuilder().parse(args[0]).getElementsByTagName("source");
        if (nodes.getLength() > 250) throw new IllegalArgumentException("Source manifest exceeds bounded batch limit");
        try (var stream = Files.newOutputStream(Path.of(args[1]))) {
            var output = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
            output.writeStartDocument(); output.writeStartElement("analysis");
            List<SourceSnapshot> batch = new ArrayList<>(); long weight = 0;
            for (int i = 0; i < nodes.getLength(); i++) {
                Path path = Path.of(((org.w3c.dom.Element) nodes.item(i)).getAttribute("path"));
                long size = Files.size(path) * 2;
                if (!batch.isEmpty() && (batch.size() >= 100 || weight + size > 4L * 1024 * 1024)) {
                    SourceAnalysis.writeBatch(batch, output); batch.clear(); weight = 0;
                }
                var source = SourceSnapshot.read(path, args.length > 2 && args[2].equals("--strip-bom"));
                batch.add(source); weight += size;
            }
            if (!batch.isEmpty()) SourceAnalysis.writeBatch(batch, output);
            output.writeEndElement(); output.writeEndDocument(); output.close();
        }
        System.out.println("Java source dependency analysis completed.");
    }
}
