package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.Context;
import com.ibm.dse.base.Tag;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

/**
 * Database lookup formatter. Queries a DB table during the FORMAT process.
 *
 * IMPORTANT for migration: This is a DB call embedded inside a format definition.
 * In the converted service, this lookup MUST be moved to the service layer.
 * The JAXB DTO must NOT contain this logic.
 *
 * Attributes:
 *   dataName    - XML element name
 *   fromTable   - DB table to query
 *   fromColumn  - column to retrieve
 *   keyValue    - context field name holding the lookup key
 */
public class CCTableFormat extends AbstractFormatElement {

    private String dataName;
    private String fromTable;
    private String fromColumn;
    private String keyValue;

    @Override
    public void initializeFrom(Tag tag) {
        this.dataName   = tag.getAttribute("dataName");
        this.fromTable  = tag.getAttribute("fromTable");
        this.fromColumn = tag.getAttribute("fromColumn");
        this.keyValue   = tag.getAttribute("keyValue");
    }

    @Override
    public String format(Context ctx) throws Exception {
        // Reads key from context, queries DB, writes result as XML element
        String key = (String) ctx.getValueAt(keyValue);
        if (key == null) return "<" + dataName + "/>";

        Connection conn = ctx.getConnection();
        String sql = "SELECT " + fromColumn + " FROM " + fromTable + " WHERE KEY = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, key);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    String result = rs.getString(1);
                    result = applyDecorators(result);
                    return "<" + dataName + ">" + result + "</" + dataName + ">";
                }
            }
        }
        return "<" + dataName + "/>";
    }

    @Override
    public void unformat(String xml, Context ctx) throws Exception {
        // CCTableFormat is output-only — typically not unformatted
        String value = extractElement(xml, dataName);
        if (value != null) ctx.setValueAt(dataName, value);
    }

    private String applyDecorators(String v) { throw new UnsupportedOperationException(); }
    private String extractElement(String x, String n) { throw new UnsupportedOperationException(); }
}
