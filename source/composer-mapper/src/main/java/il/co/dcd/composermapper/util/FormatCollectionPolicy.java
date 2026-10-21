package il.co.dcd.composermapper.util;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/** Selects effective format children using the confirmed Composer wrapper policy. */
public final class FormatCollectionPolicy {
    private static final Set<String> INDEXED = Set.of(
        "AmtaIColl", "CCIColl", "ICollFEditQry", "ICollFEditQryWEB",
        "IndexedCollectionFormatHolder", "IndexedCollectionToFormat", "IndexedCollFormat",
        "IColl", "ICollSetLength", "IndexCollectionFormatDLS", "IndexCollectionFormatDLSWEB",
        "CCIndexedCollectionFormat");

    private FormatCollectionPolicy() {}

    /** Recognizes the confirmed wrapper names exactly; other wrappers are keyed. */
    public static boolean indexed(Element wrapper) { return INDEXED.contains(wrapper.getTagName()); }

    /** Keeps indexed children in order, or the last keyed child and its attached decorators. */
    public static List<Element> children(Element wrapper, Predicate<Element> decorator) {
        var children = XmlUtil.childElements(wrapper);
        if (indexed(wrapper)) return children;
        Map<String, Element> latest = new HashMap<>();
        for (var child : children) {
            String key = key(child);
            if (!decorator.test(child) && key != null) latest.put(key, child);
        }
        List<Element> selected = new ArrayList<>();
        boolean keepDecorators = true;
        for (var child : children) {
            if (decorator.test(child)) {
                if (keepDecorators) selected.add(child);
            } else {
                String key = key(child);
                keepDecorators = key == null || latest.get(key) == child;
                if (keepDecorators) selected.add(child);
            }
        }
        return selected;
    }

    /** Tests whether a definition or a containing formatter was replaced in its own scope. */
    public static boolean effective(Element definition) {
        for (Node node = definition; node instanceof Element element; node = node.getParentNode()) {
            boolean insideFormat = hasFormatAncestor(element);
            if (!element.getTagName().equals("fmtDef") && !insideFormat) continue;
            if (!(element.getParentNode() instanceof Element parent) || indexed(parent)) continue;
            String key = key(element);
            if (key == null) continue;
            for (Node sibling = element.getNextSibling(); sibling != null; sibling = sibling.getNextSibling()) {
                if (sibling instanceof Element later && (insideFormat || later.getTagName().equals("fmtDef"))
                    && key.equals(key(later))) return false;
            }
        }
        return true;
    }

    private static boolean hasFormatAncestor(Element element) {
        for (Node node = element.getParentNode(); node instanceof Element parent; node = node.getParentNode())
            if (parent.getTagName().equals("fmtDef")) return true;
        return false;
    }

    private static String key(Element element) {
        // References point to definitions; their refid is not a newly declared collection key.
        if (element.getTagName().equals("refFmt") || element.getTagName().equals("refFormat")) return null;
        for (String attribute : List.of("id", "dataName", "name")) {
            String value = element.getAttribute(attribute);
            if (!value.isBlank()) return value;
        }
        return null;
    }
}
