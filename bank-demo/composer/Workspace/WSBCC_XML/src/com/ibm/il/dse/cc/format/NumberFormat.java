package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.math.BigDecimal;

/**
 * Numeric field formatter with decimal and thousands separator control.
 *
 * Attributes:
 *   dataName          - XML element name and context field name
 *   showThousandsSep  - "yes"|"no"
 *   showDecimalsSep   - "yes"|"no"
 *   decimalPlaces     - number of decimal places (default 2)
 */
public class NumberFormat extends AbstractFormatElement {

    private String  dataName;
    private boolean showThousandsSep = false;
    private boolean showDecimalsSep  = true;
    private int     decimalPlaces    = 2;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName         = tag.getAttribute("dataName");
        this.showThousandsSep = "yes".equalsIgnoreCase(tag.getAttribute("showThousandsSep"));
        this.showDecimalsSep  = !"no".equalsIgnoreCase(tag.getAttribute("showDecimalsSep"));
        String dp = tag.getAttribute("decimalPlaces");
        if (dp != null) this.decimalPlaces = Integer.parseInt(dp);
    }

    @Override
    public String format(Context ctx) throws Exception {
        Object val = ctx.getValueAt(dataName);
        if (val == null) return element(dataName, null, ctx);
        BigDecimal bd = new BigDecimal(String.valueOf(val));
        String formatted = formatNumber(bd);
        formatted = applyDecorators(formatted);
        return element(dataName, formatted, ctx);
    }

    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        String value = extractElement(xml, dataName);
        value = removeDecorators(value);
        if (value == null || value.isBlank()) { ctx.setValueAt(dataName, null); return; }
        // Strip formatting before storing
        value = value.replace(",", "");
        ctx.setValueAt(dataName, new BigDecimal(value));
    }

    private String formatNumber(BigDecimal bd) {
        java.text.DecimalFormat formatter = new java.text.DecimalFormat(
            showThousandsSep ? "#,##0" : "0", java.text.DecimalFormatSymbols.getInstance(java.util.Locale.ROOT));
        int places = showDecimalsSep ? decimalPlaces : 0;
        formatter.setMinimumFractionDigits(places);
        formatter.setMaximumFractionDigits(places);
        return formatter.format(bd);
    }

}
