package com.company.generated;

import java.text.SimpleDateFormat;
import java.util.Date;

/**
 * Date field formatter with configurable pattern.
 *
 * Attributes:
 *   dataName      - XML element name and context field name
 *   pattern       - Java date format pattern (e.g. "yyyyMMdd")
 *   useSep        - "yes"|"no" — whether to include separator characters
 *   fourDigYear   - "yes"|"no" — enforce 4-digit year
 *   onFailed      - "current" = use current date if parse fails
 */
public class CCDate {

    private String dataName;
    private String pattern      = "yyyyMMdd";
    private boolean useSep      = false;
    private boolean fourDigYear = true;
    private String  onFailed    = null;

    public CCDate() {
    }

    public CCDate(Tag tag) {
        initializeFrom(tag);
    }

    public void initializeFrom(Tag tag) {
        this.dataName    = tag.getAttribute("dataName");
        String p = tag.getAttribute("pattern");
        if (p != null) this.pattern = p;
        this.useSep     = "yes".equalsIgnoreCase(tag.getAttribute("useSep"));
        this.fourDigYear = !"no".equalsIgnoreCase(tag.getAttribute("fourDigYear"));
        this.onFailed   = tag.getAttribute("onFailed");
    }

    public String format(Context ctx) throws Exception {
        Object val = ctx.getValueAt(dataName);
        if (val == null) return "<" + dataName + "/>";
        SimpleDateFormat sdf = new SimpleDateFormat(pattern);
        String formatted = (val instanceof Date)
            ? sdf.format((Date) val)
            : String.valueOf(val);
        formatted = applyDecorators(formatted);
        return "<" + dataName + ">" + formatted + "</" + dataName + ">";
    }

    public void unformat(String xml, Context ctx) throws Exception {
        String value = extractElement(xml, dataName);
        if (value == null || value.isBlank()) {
            if ("current".equals(onFailed)) ctx.setValueAt(dataName, new Date());
            return;
        }
        value = removeDecorators(value);
        ctx.setValueAt(dataName, new SimpleDateFormat(pattern).parse(value));
    }

    private String applyDecorators(String v) { throw new UnsupportedOperationException(); }
    private String removeDecorators(String v) { throw new UnsupportedOperationException(); }
    private String extractElement(String x, String n) { throw new UnsupportedOperationException(); }
}