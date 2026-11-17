package il.co.dcd.verification;

import com.github.javaparser.ast.Node;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import java.util.*;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** Best-effort structural evidence from the existing resolver, never an entry/acceptance rule. */
final class ClassStructure {
    private ClassStructure() { }

    static void write(Element entry, SourceScope sources, Set<String> diagnosticTypes, XMLStreamWriter output) throws Exception {
        var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().newDocument();
        var structure = document.createElement("class-structure");
        document.appendChild(structure);
        var pending = new ArrayDeque<ResolvedReferenceTypeDeclaration>();
        var seen = new HashSet<String>();
        try { pending.add(sources.solver.solveType(entry.getAttribute("implementation"))); }
        catch (RuntimeException error) { issue(structure, "Structure root unresolved: " + entry.getAttribute("implementation"), entry.getAttribute("implementation")); }
        for (String name : diagnosticTypes) {
            try { pending.add(sources.solverFor(name).solveType(name)); }
            catch (RuntimeException error) { issue(structure, "Reachable class structure unresolved: " + name, name); }
        }
        while (!pending.isEmpty()) {
            var declaration = pending.removeFirst();
            String name = declaration.getQualifiedName();
            if (!seen.add(name)) continue;
            var item = document.createElement("class");
            item.setAttribute("name", name);
            item.setAttribute("status", "recorded");
            structure.appendChild(item);
            try {
                Optional<Node> ast = declaration.toAst();
                if (ast.isPresent() && ast.get().findCompilationUnit().isPresent()) {
                    var original = sources.evidence(ast.get().findCompilationUnit().orElseThrow());
                    item.setAttribute("source_identity", original.getAttribute("identity"));
                    item.setAttribute("source_hash", original.getAttribute("hash"));
                }
                for (var ancestor : declaration.getAncestors()) {
                    String parentName = ancestor.getQualifiedName();
                    var parent = document.createElement("parent");
                    parent.setAttribute("name", parentName);
                    var resolved = ancestor.getTypeDeclaration();
                    parent.setAttribute("relation", !declaration.isInterface() && resolved.map(value -> value.isInterface()).orElse(false)
                        ? "implements" : "extends");
                    item.appendChild(parent);
                    resolved.ifPresent(pending::addLast);
                }
            } catch (RuntimeException error) {
                issue(structure, "Inheritance or source metadata incomplete for " + name, name);
            }
            try {
                for (var field : declaration.getDeclaredFields()) {
                    try {
                        var type = field.getType();
                        while (type.isArray()) type = type.asArrayType().getComponentType();
                        if (!type.isReferenceType()) continue;
                        var reference = type.asReferenceType();
                        var member = document.createElement("field");
                        member.setAttribute("name", field.getName());
                        member.setAttribute("type", reference.getQualifiedName());
                        item.appendChild(member);
                        if (sources.typeNames.contains(reference.getQualifiedName()))
                            reference.getTypeDeclaration().ifPresent(pending::addLast);
                    } catch (RuntimeException error) {
                        issue(structure, "Field type unresolved: " + name + "." + field.getName(), name);
                    }
                }
            } catch (RuntimeException error) { issue(structure, "Field metadata incomplete for " + name, name); }
        }
        emit(structure, output);
    }

    private static void issue(Element structure, String message, String owner) {
        var item = structure.getOwnerDocument().createElement("issue");
        item.setAttribute("message", message);
        item.setAttribute("owner", owner);
        structure.appendChild(item);
    }

    private static void emit(Element element, XMLStreamWriter output) throws Exception {
        output.writeStartElement(element.getTagName());
        var attributes = element.getAttributes();
        for (int index = 0; index < attributes.getLength(); index++)
            output.writeAttribute(attributes.item(index).getNodeName(), attributes.item(index).getNodeValue());
        for (var child = element.getFirstChild(); child != null; child = child.getNextSibling())
            if (child instanceof Element item) emit(item, output);
        output.writeEndElement();
    }
}
