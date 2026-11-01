package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.time.Instant;

/** Deterministic demo timestamp: epoch text on output, no input mutation. */
public class CCSysTimeDate extends AbstractFormatElement {
    private String dataName = "ReplyTimestamp";

    @Override
    public void initializeFrom(Tag tag) {
        if (tag.getAttribute("dataName") != null) dataName = tag.getAttribute("dataName");
    }

    @Override
    public String format(Context context) {
        return element(dataName, applyDecorators(Instant.EPOCH.toString()), context);
    }

    @Override
    public void unformat(String xml, Context context) { }
}
