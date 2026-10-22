package il.co.dcd.composermapper.service;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import il.co.dcd.composermapper.parser.*;
import java.util.*;

/** Keep shared resource annotations independent of whichever consumer is visited first. */
public final class CanonicalResourceLinks {
    private CanonicalResourceLinks() {}

    /** Prepare source-channel defaults; effective consumer bindings remain in context metadata. */
    public static LinkResolver resolve(ScopedDefinitionCatalog catalog, SourceDefinitionIdentity source,
            List<String> chain, Indexes registration, Indexes index, String workspace, boolean markdown) {
        index.tagToClass().putAll(registration.tagToClass());
        index.tagToSource().putAll(registration.tagToSource());
        String folder = source.kind().equals("format") ? "formats" : source.kind().equals("context") ? "contexts" : "classes";
        Map<String, String> paths = new LinkedHashMap<>();
        paths.put(folder + ":" + source.name(), OperationDependencyConnections.resourcePath(source, workspace));
        if (source.kind().equals("format")) {
            var format = new FormatFileParser().parseEffectiveDefinition(source.element(), source.file(), index);
            for (String name : format.getReferencedMappedJavaClasses()) {
                var candidates = catalog.candidates("java_class", name, chain, null);
                if (candidates.size() != 1) continue;
                var candidate = candidates.getFirst();
                index.classToSource().put(name, candidate.file());
                paths.put("classes:" + name, OperationDependencyConnections.resourcePath(candidate, workspace));
            }
        } else if (source.kind().equals("context")) {
            String parent = new ContextFileParser().parseDefinition(source.element(), source.file()).getParent();
            if (parent != null && !parent.isBlank() && !parent.equalsIgnoreCase("nil")) {
                try {
                    var target = catalog.resolve("context", parent, chain, owner(source));
                    if (target != null) {
                        index.contextToSource().put(parent, target.file());
                        paths.put("contexts:" + parent, OperationDependencyConnections.resourcePath(target, workspace));
                    }
                } catch (IllegalArgumentException ambiguity) {
                    // The effective connection reports ambiguity; a source note must not pick a candidate.
                }
            }
        }
        return new LinkResolver(markdown, paths);
    }

    private static SourceDefinitionIdentity owner(SourceDefinitionIdentity source) {
        if (source.owner().isEmpty() || source.element() == null) return null;
        org.w3c.dom.Node parent = source.element().getParentNode();
        while (parent instanceof org.w3c.dom.Element element) {
            if (element.getTagName().equals("CCDSEServerOperation"))
                return new SourceDefinitionIdentity("operation", element.getAttribute("id"), source.channel(),
                    source.file(), source.relativePath(), source.owner(), "", element);
            parent = parent.getParentNode();
        }
        return null;
    }
}
