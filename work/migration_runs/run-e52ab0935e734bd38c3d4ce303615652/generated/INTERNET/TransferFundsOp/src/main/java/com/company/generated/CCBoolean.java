package com.company.generated;

/**
 * Boolean field formatter. Maps "true"/"false" XML values to/from context.
 *
 * Attributes:
 *   dataName - the XML element name and context field name
 *   trueValue  - XML string representing true  (default: "true")
 *   falseValue - XML string representing false (default: "false")
 */
public class CCBoolean {

    private String dataName;
    private String trueValue  = "true";
    private String falseValue = "false";

    public void initializeFrom(Tag tag) {
        this.dataName   = tag.getAttribute("dataName");
        String tv = tag.getAttribute("trueValue");
        if (tv != null) this.trueValue = tv;
        String fv = tag.getAttribute("falseValue");
        if (fv != null) this.falseValue = fv;
    }

    public String format(Context ctx) throws Exception {
        Object val = ctx.getValueAt(dataName);
        boolean b = Boolean.TRUE.equals(val) || "true".equalsIgnoreCase(String.valueOf(val));
        return "<" + dataName + ">" + (b ? trueValue : falseValue) + "</" + dataName + ">";
    }

    public void unformat(String xml, Context ctx) throws Exception {
        String value = extractElement(xml, dataName);
        ctx.setValueAt(dataName, trueValue.equalsIgnoreCase(value));
    }

    private String extractElement(String xml, String name) { throw new UnsupportedOperationException(); }
}