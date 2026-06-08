package il.co.dcd.composermapper.parser;

import il.co.dcd.composermapper.model.*;
import il.co.dcd.composermapper.util.XmlUtil;
import org.w3c.dom.*;

import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;

public class OperationFileParser {

    /** Matches on{N}Do transition attributes */
    private static final Pattern ON_N_DO    = Pattern.compile("^on\\d+Do$");
    /** Matches on{N}Return body-switch attributes */
    private static final Pattern ON_N_RETURN = Pattern.compile("^on(\\d+)Return$");
    /** Reserved attribute names that are not business parameters */
    private static final Set<String> RESERVED = Set.of(
        "id", "implClass", "onOtherDo", "onOtherDoDefault", "onTimeoutDo", "onlyFor");

    public List<OperationDef> parse(Path xml) {
        List<OperationDef> out = new ArrayList<>();
        walk(XmlUtil.parse(xml).getDocumentElement(), xml, out);
        return out;
    }

    private void walk(Element e, Path xml, List<OperationDef> out) {
        if (tagEquals(e, "CCDSEServerOperation")) out.add(parseOperation(e, xml));
        for (Element c : XmlUtil.childElements(e)) walk(c, xml, out);
    }

    private OperationDef parseOperation(Element e, Path xml) {
        OperationDef op = new OperationDef();
        op.setId(XmlUtil.attr(e, "id"));
        op.setOperationContext(XmlUtil.attr(e, "operationContext"));
        op.setSourceFile(xml);

        // operation-level attributes
        op.setHostKey(XmlUtil.attr(e, "hostKey"));
        op.setOperationFields(XmlUtil.attr(e, "operationFields"));
        op.setWriteToLog(XmlUtil.attr(e, "writeToLog"));
        op.setWriteToOfecStat(XmlUtil.attr(e, "writeToOfecStat"));
        op.setIsSelectiveJournalising(XmlUtil.attr(e, "isSelectiveJournalising"));

        for (int i = 0; i < e.getAttributes().getLength(); i++) {
            var a = e.getAttributes().item(i);
            op.getRawAttributes().put(a.getNodeName(), a.getNodeValue());
        }

        for (Element c : XmlUtil.childElements(e)) {
            switch (c.getTagName().toLowerCase(Locale.ROOT)) {
                case "opstep"     -> op.getSteps().add(parseStep(c, op.getId(), xml));
                case "refformat"  -> { String n = XmlUtil.attrIgnoreCase(c, "name"), r = XmlUtil.attrIgnoreCase(c, "refid");
                                       if (n != null && r != null) op.getRefFormats().put(n, r); }
                case "fmtdef"     -> { String id = XmlUtil.attrIgnoreCase(c, "id");
                                       if (id != null && !id.isBlank()) op.getInlineFormatIds().add(id); }
                case "inivalue"   -> { String v = XmlUtil.attrIgnoreCase(c, "id");
                                       if (v != null && !v.isBlank()) op.getIniValues().add(v); }
            }
        }
        return op;
    }

    private OpStepDef parseStep(Element e, String opId, Path xml) {
        OpStepDef s = new OpStepDef();
        s.setId(XmlUtil.attr(e, "id"));
        s.setParentOperationId(opId);
        s.setImplClass(XmlUtil.attr(e, "implClass"));
        s.setSourceFile(xml);
        s.setOnlyFor(XmlUtil.attr(e, "onlyFor"));

        for (int i = 0; i < e.getAttributes().getLength(); i++) {
            var a    = e.getAttributes().item(i);
            String name  = a.getNodeName();
            String value = a.getNodeValue();
            s.getRawAttributes().put(name, value);

            if ("onOtherDo".equals(name) || "onOtherDoDefault".equals(name)
                    || "onTimeoutDo".equals(name) || name.startsWith("on") && name.endsWith("Do")) {
                // transition: on{N}Do, onOtherDo, onOtherDoDefault, onTimeoutDo
                s.getTransitions().put(name, value);
            } else if (ON_N_RETURN.matcher(name).matches()) {
                // error body switch: on{N}Return
                var m = ON_N_RETURN.matcher(name);
                m.matches();
                s.getReturnBodySwitches().put(m.group(1), value);
            } else if (!RESERVED.contains(name)) {
                s.getParameters().put(name, value);
            }
        }
        return s;
    }

    private boolean tagEquals(Element e, String name) {
        return e.getTagName().equalsIgnoreCase(name);
    }
}
