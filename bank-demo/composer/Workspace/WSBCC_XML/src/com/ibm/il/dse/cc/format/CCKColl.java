package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Key-value collection formatter. Maps a set of named fields to/from context
 * as a structured block. Unlike CCIColl (which iterates a list), CCKColl
 * represents a fixed set of named fields grouped under a single XML element.
 *
 * Attributes:
 *   dataName - the XML element wrapper name
 *
 * On format: formats each child formatter tag as a named XML element.
 * On unformat: reads each named XML element and stores in context by name.
 *
 * Example usage: balance block with AvailableBalance, BookBalance, HoldAmount.
 */
public class CCKColl extends AbstractFormatElement {

    private String dataName;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName = tag.getAttribute("dataName");
    }

    @Override
    public String format(Context ctx) throws Exception {
        return "<" + dataName + ">" + formatChildren(ctx) + "</" + dataName + ">";
    }

    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        String inner = extractElement(xml, dataName);
        unformatChildren(inner, ctx);
    }

    private String formatChildren(Context ctx) throws Exception { throw new UnsupportedOperationException(); }
    private void unformatChildren(String xml, Context ctx) throws Exception { throw new UnsupportedOperationException(); }
    private String extractElement(String xml, String name) { throw new UnsupportedOperationException(); }
}
