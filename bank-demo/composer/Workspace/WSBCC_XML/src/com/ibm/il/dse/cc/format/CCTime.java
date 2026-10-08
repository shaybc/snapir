package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.util.Date;

/** Thin demo time formatter with deterministic dummy values for conversion fixtures. */
public class CCTime {
    private String dataName = "ExecutionTime";

    /** Keep the configured XML/context field name used by the demo formats. */
    public void initializeFrom(Tag tag) {
        String configuredName = tag.getAttribute("dataName");
        if (configuredName != null && !configuredName.isBlank()) {
            dataName = configuredName;
        }
    }

    /** Return a sample time element; the demo deliberately ignores the actual time value. */
    public String format(Context context) throws Exception {
        return "<" + dataName + ">00:00:00</" + dataName + ">";
    }

    /** Populate the named field with a dummy Date; input parsing is outside this fixture. */
    public void unformat(String xml, Context context) throws Exception {
        context.setValueAt(dataName, new Date(0L));
    }
}
