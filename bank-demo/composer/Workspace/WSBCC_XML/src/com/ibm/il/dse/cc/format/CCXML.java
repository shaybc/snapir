package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;

/**
 * XML container formatter. Groups child formatter tags into an XML element.
 *
 * Key attributes:
 *   dataName       - the XML element name
 *   transparent    - when "true", the wrapper element is NOT emitted on the wire;
 *                    child fields appear at the parent level
 *   unnamed        - controls whether dataName appears as the element name
 *
 * Any formatter type (including CCXML itself) can have decorators following it.
 */
public class CCXML extends AbstractFormatElement {

    private String  dataName;
    private boolean transparent = false;
    private boolean unnamed     = false;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName    = tag.getAttribute("dataName");
        String t = tag.getAttribute("transparent");
        if ("true".equalsIgnoreCase(t)) this.transparent = true;
        String u = tag.getAttribute("unnamed");
        if ("true".equalsIgnoreCase(u)) this.unnamed = true;
        super.initializeFrom(tag);
    }

    @Override
    public String format(Context ctx) throws Exception {
        // If transparent=true, do not emit the wrapper element
        if (transparent) {
            return formatChildren(ctx);
        }
        return "<" + dataName + ">" + formatChildren(ctx) + "</" + dataName + ">";
    }

    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        // If transparent=true, parse children directly from the parent level
        if (transparent) {
            unformatChildren(xml, ctx);
        } else {
            String inner = extractElement(xml, dataName);
            unformatChildren(inner, ctx);
        }
    }

    private String formatChildren(Context ctx) throws Exception {
        throw new UnsupportedOperationException("Runtime method");
    }
    private void unformatChildren(String xml, Context ctx) throws Exception {
        throw new UnsupportedOperationException("Runtime method");
    }
    private String extractElement(String xml, String name) {
        throw new UnsupportedOperationException("Runtime method");
    }
}
