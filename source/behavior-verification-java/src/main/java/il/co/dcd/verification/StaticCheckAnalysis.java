package il.co.dcd.verification;

import il.co.dcd.verification.harness.BoundaryValues;
import java.nio.file.*;
import java.util.Map;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.stream.XMLOutputFactory;

/** Standalone static checks; never runs original or generated classes. */
public final class StaticCheckAnalysis {
    private StaticCheckAnalysis() { }
    public static void main(String[] args) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        var root = factory.newDocumentBuilder().parse(Path.of(args[0]).toFile()).getDocumentElement();
        Map<String, Object> report = Map.of("native", NativeInspection.inspect(BoundaryValues.child(root, "native")),
            "proofs", StaticExclusionAnalysis.inspect(BoundaryValues.child(root, "legacy")),
            "settings", OriginalSettingsInspection.inspect(BoundaryValues.child(root, "legacy")),
            "preparation", ConfigurationPreparation.inspect(BoundaryValues.child(root, "legacy")));
        try (var stream = Files.newOutputStream(Path.of(args[1]))) {
            var output = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
            output.writeStartDocument();
            BoundaryValues.write(output, "value", report);
            output.writeEndDocument(); output.close();
        }
    }
}
