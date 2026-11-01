package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.util.List;
import java.util.ArrayList;
import java.util.Map;

/**
 * Index-based collection formatter. Iterates a List stored in the context
 * and applies child formatters to each element.
 *
 * Attributes:
 *   dataName - context field name holding the List, and the XML element wrapper
 *   times    - maximum iterations ("*" = unlimited)
 *
 * On format: iterates context[dataName] List, formats each item using child formatters.
 * On unformat: collects child XML blocks into a List, stores in context[dataName].
 *
 * Any formatter type can have decorators — including CCIColl itself.
 */
public class CCIColl extends AbstractFormatElement {

    private String dataName;
    private int    maxTimes = Integer.MAX_VALUE;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName = tag.getAttribute("dataName");
        String times = tag.getAttribute("times");
        if (times != null && !"*".equals(times)) {
            this.maxTimes = Integer.parseInt(times);
        }
    }

    @Override
    public String format(Context ctx) throws Exception {
        List<?> items = (List<?>) ctx.getValueAt(dataName);
        if (items == null) return "";
        StringBuilder sb = new StringBuilder();
        int count = Math.min(items.size(), maxTimes);
        for (int i = 0; i < count; i++) {
            sb.append(formatItem(items.get(i), ctx, i));
        }
        return sb.toString();
    }

    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        List<Map<String, Object>> items = new ArrayList<>();
        if (childFormats().size() != 1 || !(childFormats().get(0) instanceof CCXML)) {
            throw new IllegalStateException("Demo indexed collections require one named CCXML item");
        }
        CCXML child = (CCXML) childFormats().get(0);
        for (String fragment : DemoXml.elements(xml, child.getElementName())) {
            if (items.size() >= maxTimes) break;
            Context item = new Context();
            child.unformat(fragment, item);
            items.add(item.snapshot());
        }
        ctx.setValueAt(dataName, items);
    }

    private String formatItem(Object item, Context ctx, int index) throws Exception {
        if (!(item instanceof Map)) throw new IllegalArgumentException("Demo collection item must be a map at " + index);
        return formatChildren(ctx.copyWith((Map<String, ?>) item));
    }
}
