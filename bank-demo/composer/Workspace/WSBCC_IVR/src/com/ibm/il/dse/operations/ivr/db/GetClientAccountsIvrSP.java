package com.ibm.il.dse.operations.ivr.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.*;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * IVR-specific account list retrieval. Uses PIN authentication.
 * Returns simplified account data (no nickname, no open date) for IVR.
 *
 * Context reads: ClientId, Pin
 * Context writes: Accounts (List of Map), TotalAccountCount
 *
 * Returns: 0=success, 4=not found, 8=db error
 */
public class GetClientAccountsIvrSP extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_IVR.GET_CLIENT_ACCOUNTS_IVR(?,?,?,?)}";

    @Override
    public int execute() throws Exception {
        Context ctx      = getContext();
        String clientId  = (String) ctx.getValueAt("ClientId");
        String pin       = (String) ctx.getValueAt("Pin");

        Connection conn  = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, clientId);
            cs.setString(2, pin);
            cs.registerOutParameter(3, Types.VARCHAR);
            cs.registerOutParameter(4, Types.REF_CURSOR);
            cs.execute();

            String spRc = cs.getString(3);
            if ("NOT_FOUND".equals(spRc) || "AUTH_FAILED".equals(spRc)) return 4;

            try (ResultSet rs = (ResultSet) cs.getObject(4)) {
                List<Map<String, Object>> accounts = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> a = new LinkedHashMap<>();
                    a.put("AccountNumber",   rs.getString("ACCOUNT_NUMBER"));
                    a.put("AccountTypeCode", rs.getString("ACCOUNT_TYPE_CODE"));
                    a.put("AvailableBalance",rs.getBigDecimal("AVAILABLE_BALANCE"));
                    a.put("Currency",        rs.getString("CURRENCY_CODE"));
                    accounts.add(a);
                }
                if (accounts.isEmpty()) return 4;
                ctx.setValueAt("Accounts",          accounts);
                ctx.setValueAt("TotalAccountCount", String.valueOf(accounts.size()));
            }
        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return 8;
        }
        return 0;
    }
}
