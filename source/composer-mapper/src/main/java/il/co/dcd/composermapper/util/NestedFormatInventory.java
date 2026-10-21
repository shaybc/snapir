package il.co.dcd.composermapper.util;

import il.co.dcd.composermapper.model.SourceDefinitionIdentity;
import java.util.ArrayList;
import java.util.List;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/** Allocates inventory notes for named format occurrences within a parent format. */
public final class NestedFormatInventory {
    private NestedFormatInventory() {}

    /** Returns the nearest named format ancestor, retaining its exact XML selector. */
    public static SourceDefinitionIdentity parent(SourceDefinitionIdentity source) {
        String selector = source.selector();
        for (Node node = source.element().getParentNode(); node instanceof Element element; node = node.getParentNode()) {
            selector = selector.substring(0, selector.lastIndexOf('/'));
            String name = XmlUtil.attr(element, "id");
            if (element.getTagName().equals("fmtDef") && name != null && !name.isBlank()) {
                return new SourceDefinitionIdentity("format", name, source.channel(), source.file(),
                    source.relativePath(), selector, source.owner(), element);
            }
        }
        return null;
    }

    /** Counts named child formats in document order, across wrappers but excluding deeper scopes. */
    public static int ordinal(SourceDefinitionIdentity source, SourceDefinitionIdentity parent) {
        List<Element> nested = new ArrayList<>();
        collect(parent.element(), nested);
        for (int i = 0; i < nested.size(); i++) if (nested.get(i) == source.element()) return i + 1;
        throw new IllegalArgumentException("Nested format is absent from parent: " + source.selector());
    }

    private static void collect(Element parent, List<Element> nested) {
        for (Element child : XmlUtil.childElements(parent)) {
            String name = XmlUtil.attr(child, "id");
            if (child.getTagName().equals("fmtDef") && name != null && !name.isBlank()) nested.add(child);
            else collect(child, nested);
        }
    }

    /** Keeps top-level paths and places nested occurrences beneath their parent's note stem. */
    public static String path(String prefix, SourceDefinitionIdentity source) {
        SourceDefinitionIdentity parent = parent(source);
        if (parent == null) return ScopedVaultPaths.inventory(prefix, "formats", source.relativePath(),
            source.selector(), source.name());
        String parentPath = path(prefix, parent);
        return parentPath.substring(0, parentPath.length() - 3) + "/nested/" + ordinal(source, parent)
            + "/" + ScopedVaultPaths.segment(source.name()) + ".md";
    }
}
