package il.co.dcd.composermapper.parser;

import il.co.dcd.composermapper.index.Indexes;
import il.co.dcd.composermapper.model.*;
import il.co.dcd.composermapper.util.XmlUtil;
import org.w3c.dom.*;

import java.nio.file.Path;
import java.util.*;

public class FormatFileParser {

    public List<FormatDef> parse(Path xml, Indexes x) {
        List<FormatDef> out = new ArrayList<>();
        walk(XmlUtil.parse(xml).getDocumentElement(), xml, x, out);
        return out;
    }

    private void walk(Element e, Path xml, Indexes x, List<FormatDef> out) {
        if ("fmtDef".equals(e.getTagName())) out.add(parseFormat(e, xml, x));
        for (Element c : XmlUtil.childElements(e)) walk(c, xml, x, out);
    }

    private FormatDef parseFormat(Element e, Path xml, Indexes x) {
        FormatDef f = new FormatDef();
        f.setId(XmlUtil.attr(e, "id"));
        f.setSourceFile(xml);

        List<Element> children = XmlUtil.childElements(e);
        if (!children.isEmpty()) {
            Element root = children.get(0);
            f.setRootTag(toNode(root, f, x, "/" + nodeSegment(root), children, 0));
        }
        return f;
    }

    /**
     * Converts an Element to a TagNode, attaching decorator siblings to the
     * formatter node they follow rather than as peer children of the parent.
     *
     * @param siblings  the full sibling list of this element's parent -- used to
     *                  detect and attach immediately following decorator tags
     * @param selfIndex index of this element within siblings (-1 if unknown/root)
     */
    private TagNode toNode(Element e, FormatDef f, Indexes x, String path,
                           List<Element> siblings, int selfIndex) {
        TagNode n = new TagNode(e.getTagName());

        // collect attributes
        for (int i = 0; i < e.getAttributes().getLength(); i++) {
            var a = e.getAttributes().item(i);
            n.getAttributes().put(a.getNodeName(), a.getNodeValue());
            captureSerializationFlag(e, a, f, path);
            String lower = (a.getNodeName() + "=" + a.getNodeValue()).toLowerCase();
            if (lower.contains("table") || lower.contains("column")
                    || lower.contains("sql")  || lower.contains("jdbc"))
                f.getInferredExternalDependencies().add("Database");
            if (lower.contains("url")  || lower.contains("endpoint")
                    || lower.contains("service") || lower.contains("soap")
                    || lower.contains("http"))
                f.getInferredExternalDependencies().add("API/Service");
        }

        captureDatabaseLookup(e, n, f);
        f.getReferencedXmlTags().add(e.getTagName());
        String mapped = x.tagToClass().get(e.getTagName());
        if (mapped != null) f.getReferencedMappedJavaClasses().add(mapped);

        // attach decorators that immediately follow this node in the sibling list
        if (selfIndex >= 0) {
            int next = selfIndex + 1;
            while (next < siblings.size() && isDecorator(siblings.get(next), x)) {
                Element decEl = siblings.get(next);
                TagNode decNode = new TagNode(decEl.getTagName());
                for (int i = 0; i < decEl.getAttributes().getLength(); i++) {
                    var a = decEl.getAttributes().item(i);
                    decNode.getAttributes().put(a.getNodeName(), a.getNodeValue());
                }
                n.getDecorators().add(decNode);
                f.getReferencedXmlTags().add(decEl.getTagName());
                String decMapped = x.tagToClass().get(decEl.getTagName());
                if (decMapped != null) f.getReferencedMappedJavaClasses().add(decMapped);
                next++;
            }
        }

        // recurse into children, passing the child list so decorator attachment works
        List<Element> childElements = XmlUtil.childElements(e);
        Set<Integer> decoratorIndices = new HashSet<>();

        // first pass: identify which child indices are decorators consumed by a formatter
        for (int i = 0; i < childElements.size(); i++) {
            if (!decoratorIndices.contains(i) && !isDecorator(childElements.get(i), x)) {
                // this is a formatter child -- count how many decorators follow it
                int j = i + 1;
                while (j < childElements.size() && isDecorator(childElements.get(j), x)) {
                    decoratorIndices.add(j);
                    j++;
                }
            }
        }

        // second pass: build child TagNodes for non-decorator children only
        for (int i = 0; i < childElements.size(); i++) {
            if (!decoratorIndices.contains(i)) {
                Element child = childElements.get(i);
                TagNode childNode = toNode(child, f, x,
                        path + "/" + nodeSegment(child), childElements, i);
                n.getChildren().add(childNode);
            }
        }

        return n;
    }

    private boolean isDecorator(Element e, Indexes x) {
        String tagName = e.getTagName();
        String fqcn    = x.tagToClass().get(tagName);
        if (fqcn == null) return false;
        return fqcn.toLowerCase().contains("decorator");
    }

    private void captureSerializationFlag(Element e, Node a, FormatDef f, String path) {
        String attrName = a.getNodeName();
        if (!"transparent".equals(attrName) && !"unnamed".equals(attrName)) return;
        String dataName      = e.getAttribute("dataName");
        String nodeIdentifier = (dataName != null && !dataName.isBlank())
                ? dataName : "path=" + path;
        f.getSerializationFlags().add(nodeIdentifier + " " + attrName + "=" + a.getNodeValue());
    }

    private String nodeSegment(Element e) {
        return e.getTagName() + "[" + siblingPosition(e) + "]";
    }

    private int siblingPosition(Element e) {
        int position = 1;
        for (Node n = e.getPreviousSibling(); n != null; n = n.getPreviousSibling())
            if (n instanceof Element prev && prev.getTagName().equals(e.getTagName()))
                position++;
        return position;
    }

    private void captureDatabaseLookup(Element e, TagNode n, FormatDef f) {
        String fromTable  = n.getAttributes().get("fromTable");
        String fromColumn = n.getAttributes().get("fromColumn");
        String keyValue   = n.getAttributes().get("keyValue");
        if (fromTable != null || fromColumn != null || keyValue != null) {
            f.getInferredExternalDependencies().add("Database");
            f.getDatabaseLookups().add(
                new FormatDef.DatabaseLookup(e.getTagName(), fromTable, fromColumn, keyValue));
        }
    }
}
