package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;

/** Demo constant field emits its configured value and ignores incoming values. */
public class CCConstant extends AbstractFormatElement {
    private String dataName;
    private String value = "";

    @Override
    public void initializeFrom(Tag tag) {
        dataName = tag.getAttribute("dataName");
        if (tag.getAttribute("value") != null) value = tag.getAttribute("value");
    }

    @Override
    public String format(Context context) { return element(dataName, applyDecorators(value), context); }

    @Override
    public void unformat(String xml, Context context) { }
}
