package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Fetches personalised navigation links for a client.
 * Simple reference operation — good as a pilot example.
 *
 * Context reads: ClientId, BankId
 * Context writes: Links (List of Map)
 *
 * Returns:
 *   0 - links found and loaded
 *   4 - no links configured for this client
 *   8 - database error
 */
public class GetClientLinksSP extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_PORTAL.GET_CLIENT_LINKS(?,?,?,?)}";
    private static final int RC_SUCCESS   = 0;
    private static final int RC_NOT_FOUND = 4;
    private static final int RC_DB_ERROR  = 8;

    @Override
    public int execute() throws Exception {
        Context ctx      = getContext();
        String clientId  = (String) ctx.getValueAt("ClientId");
        String bankId    = (String) ctx.getValueAt("BankId");

        Connection conn  = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, clientId);
            cs.setString(2, bankId);
            cs.registerOutParameter(3, java.sql.Types.VARCHAR);
            cs.registerOutParameter(4, java.sql.Types.REF_CURSOR);
            cs.execute();

            String spRc = cs.getString(3);
            if ("NOT_FOUND".equals(spRc)) return RC_NOT_FOUND;

            try (ResultSet rs = (ResultSet) cs.getObject(4)) {
                List<Map<String, Object>> links = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> link = new LinkedHashMap<>();
                    link.put("LinkId",   rs.getString("LINK_ID"));
                    link.put("LinkUrl",  rs.getString("LINK_URL"));
                    link.put("IsExternal", "Y".equals(rs.getString("IS_EXTERNAL")));
                    link.put("IconCode", rs.getString("ICON_CODE"));
                    links.add(link);
                }
                if (links.isEmpty()) return RC_NOT_FOUND;
                ctx.setValueAt("Links", links);
            }

        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
        return RC_SUCCESS;
    }
}
