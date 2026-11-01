package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import java.util.*;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;

/** Extract syntax only from the existing conservative graph; never execute or judge equivalence. */
final class ParserChecklist {
    final ReachableSlice graph;
    final Map<String, ChecklistItem> items = new TreeMap<>();
    final Set<String> issues = new TreeSet<>();

    ParserChecklist(ReachableSlice graph) { this.graph = graph; }

    ChecklistItem add(CodeNode owner, Node site, String kind, String detail) {
        ChecklistItem item = new ChecklistItem(owner, site, kind, detail);
        return items.computeIfAbsent(item.id, ignored -> item);
    }

    void analyze() {
        ChecklistSyntax syntax = new ChecklistSyntax(this);
        for (CodeNode node : graph.nodes.values()) {
            try {
                if (node.anchor instanceof com.github.javaparser.ast.body.CallableDeclaration<?> callable) {
                    for (var type : callable.getThrownExceptions()) add(node, type, "exception", "declared")
                        .property("exception_type", type.toString());
                }
                if (!node.kind.equals("method")) {
                    var item = add(node, node.anchor, "initialization", node.kind);
                    if (node.kind.endsWith("_field_default")) {
                        var type = ((com.github.javaparser.ast.body.VariableDeclarator) node.anchor).getType();
                        String value = !type.isPrimitiveType() ? "null" : switch (type.asString()) {
                            case "boolean" -> "false";
                            case "char" -> "\\u0000";
                            case "float", "double" -> "0.0";
                            default -> "0";
                        };
                        item.property("rule", "java_default_value").property("value", value);
                    }
                } else if (graph.roots.getOrDefault("initialization", Set.of()).contains(node.id)) {
                    add(node, node.anchor, "initialization", "configured_setup_method");
                }
                if (node.body != null) syntax.scan(node.body, node);
            } catch (RuntimeException exception) {
                issues.add("Checklist did not finish for " + node.signature + ": " + exception.getClass().getSimpleName());
            }
        }
        new ChecklistCalls(this).analyze();
    }

    void write(XMLStreamWriter output) throws XMLStreamException {
        output.writeStartElement("checklist");
        output.writeAttribute("schema_version", "parser-checklist-v1");
        output.writeAttribute("status", issues.isEmpty() ? "extracted" : "verification_incomplete");
        for (ChecklistItem item : items.values()) item.write(output);
        for (String issue : issues) {
            output.writeEmptyElement("issue"); output.writeAttribute("message", issue);
        }
        output.writeEndElement();
    }
}
