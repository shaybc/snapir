package il.co.dcd.verification;

import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.javassistmodel.JavassistMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JarTypeSolver;
import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.zip.ZipFile;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;
import org.w3c.dom.Element;

/** Identify configured binary ownership without changing method-selection rules. */
final class FrameworkJars {
    private final Element scope;
    private final Map<String, Element> owners = new HashMap<>();
    private final Map<String, String> binaryNames = new HashMap<>();
    private final Set<String> ambiguous = new HashSet<>();
    private final List<Element> libraries = new ArrayList<>();
    final Set<String> entries = new HashSet<>();

    FrameworkJars(Element scope) {
        this.scope = scope;
        for (var node = scope.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (!(node instanceof Element library) || !library.getTagName().equals("framework-library")) continue;
            libraries.add(library);
            var classes = library.getElementsByTagName("class");
            for (int index = 0; index < classes.getLength(); index++) {
                String binary = ((Element) classes.item(index)).getAttribute("name");
                String name = binary.replace('$', '.');
                var previous = owners.putIfAbsent(name, library);
                if (previous != null && !previous.getAttribute("path").equals(library.getAttribute("path"))) ambiguous.add(name);
                binaryNames.put(name, binary);
            }
        }
    }

    void addTo(CombinedTypeSolver solver) throws IOException {
        for (var library : libraries) solver.add(new JarTypeSolver(Path.of(library.getAttribute("path"))));
    }

    private Element owner(ResolvedMethodDeclaration method) {
        if (!(method instanceof JavassistMethodDeclaration)) return null;
        String name = method.declaringType().getQualifiedName().replace('$', '.');
        var library = owners.get(name);
        if (library == null) return null;
        if (ambiguous.contains(name)) throw new IllegalStateException("Framework class occurs in multiple configured JARs: " + name);
        // Never label a method as framework code when another project archive can own the same type.
        var projectLibraries = scope.getElementsByTagName("library");
        for (int index = 0; index < projectLibraries.getLength(); index++) {
            var candidate = (Element) projectLibraries.item(index);
            if (candidate.getAttribute("path").equals(library.getAttribute("path"))) continue;
            try (var archive = new ZipFile(candidate.getAttribute("path"))) {
                if (archive.getEntry(binaryNames.get(name).replace('.', '/') + ".class") != null)
                    throw new IllegalStateException("Framework class ownership conflicts with another project JAR: " + name);
            } catch (IOException error) {
                throw new IllegalStateException("Framework class ownership could not be verified: " + name, error);
            }
        }
        return library;
    }

    boolean write(Element entry, ResolvedMethodDeclaration method, XMLStreamWriter output) throws XMLStreamException {
        var library = owner(method);
        if (library == null) return false;
        if (method.isAbstract()) throw new IllegalStateException("Entry method has no executable body");
        output.writeStartElement("framework-method");
        output.writeAttribute("implementation_class", entry.getAttribute("implementation"));
        output.writeAttribute("declaring_class", method.declaringType().getQualifiedName());
        output.writeAttribute("signature", method.getQualifiedSignature());
        output.writeAttribute("method", method.getName());
        output.writeAttribute("return_type", method.getReturnType().describe());
        output.writeAttribute("jar_path", library.getAttribute("path"));
        output.writeAttribute("jar_sha256", library.getAttribute("sha256"));
        for (int index = 0; index < method.getNumberOfParams(); index++) {
            output.writeEmptyElement("parameter");
            output.writeAttribute("type", method.getParam(index).getType().describe());
        }
        output.writeEndElement();
        entries.add(entry.getAttribute("id"));
        return true;
    }
}
