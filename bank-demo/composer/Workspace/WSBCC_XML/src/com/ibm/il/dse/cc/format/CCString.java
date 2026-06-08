package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;

/**
 * String field formatter. Maps a single XML element to/from a context field.
 *
 * Attributes:
 *   dataName - the XML element name AND the context field name
 *
 * Any decorators that immediately follow this tag in the XML definition
 * are applied to the string value (addDecoration on format, removeDecoration
 * in reverse order on unformat).
 */
public class CCString extends AbstractFormatElement {

    private String dataName;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName = tag.getAttribute("dataName");
    }

    /** format: reads context[dataName] -> applies decorators -> emits XML element */
    @Override
    public String format(Context ctx) throws Exception {
        String value = (String) ctx.getValueAt(dataName);
        value = applyDecorators(value);          // addDecoration chain (forward order)
        return "<" + dataName + ">" + value + "</" + dataName + ">";
    }

    /** unformat: reads XML element -> applies decorators in reverse -> writes context[dataName] */
    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        String value = extractElement(xml, dataName);
        value = removeDecorators(value);         // removeDecoration chain (reverse order)
        ctx.setValueAt(dataName, value);
    }

    private String applyDecorators(String v)  { throw new UnsupportedOperationException(); }
    private String removeDecorators(String v)  { throw new UnsupportedOperationException(); }
    private String extractElement(String xml, String name) { throw new UnsupportedOperationException(); }
}
