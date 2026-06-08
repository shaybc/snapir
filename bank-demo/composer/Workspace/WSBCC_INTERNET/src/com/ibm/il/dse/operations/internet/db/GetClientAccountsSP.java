package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Types;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Fetches all accounts for a client from the core banking database.
 *
 * XML attributes: none (uses context fields directly)
 *
 * Context reads:
 *   ClientId        - the client identifier
 *   BankId          - bank identifier (padded to 4 chars)
 *   IncludeInactive - boolean flag
 *
 * Context writes:
 *   Accounts        - List of Map objects (one per account)
 *   ClientFullName  - client full name from DB
 *   TotalAccountCount - string count
 *
 * Returns:
 *   0 - accounts found and loaded successfully
 *   4 - no accounts found for this client
 *   8 - database error
 */
public class GetClientAccountsSP extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_ACCOUNTS.GET_CLIENT_ACCOUNTS(?,?,?,?,?,?)}";
    private static final int    RC_SUCCESS    = 0;
    private static final int    RC_NOT_FOUND  = 4;
    private static final int    RC_DB_ERROR   = 8;

    @Override
    public int execute() throws Exception {
        Context ctx = getContext();

        String  clientId       = (String)  ctx.getValueAt("ClientId");
        String  bankId         = (String)  ctx.getValueAt("BankId");
        Boolean includeInactive = (Boolean) ctx.getValueAt("IncludeInactive");
        if (includeInactive == null) includeInactive = false;

        Connection conn = ctx.getConnection();

        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            // IN parameters
            cs.setString(1, clientId);
            cs.setString(2, bankId);
            cs.setString(3, includeInactive ? "Y" : "N");

            // OUT parameters
            cs.registerOutParameter(4, Types.VARCHAR);   // client full name
            cs.registerOutParameter(5, Types.VARCHAR);   // return code
            cs.registerOutParameter(6, Types.REF_CURSOR); // accounts cursor

            cs.execute();

            String spReturnCode = cs.getString(5);
            if ("NOT_FOUND".equals(spReturnCode)) return RC_NOT_FOUND;

            String clientFullName = cs.getString(4);
            ctx.setValueAt("ClientFullName", clientFullName);

            try (ResultSet rs = (ResultSet) cs.getObject(6)) {
                List<Map<String, Object>> accounts = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> account = new LinkedHashMap<>();
                    account.put("AccountNumber",    rs.getString("ACCOUNT_NUMBER"));
                    account.put("AccountTypeCode",  rs.getString("ACCOUNT_TYPE_CODE"));
                    account.put("AccountNickname",  rs.getString("ACCOUNT_NICKNAME"));
                    account.put("AvailableBalance", rs.getBigDecimal("AVAILABLE_BALANCE"));
                    account.put("Currency",         rs.getString("CURRENCY_CODE"));
                    account.put("IsActive",         "Y".equals(rs.getString("IS_ACTIVE")));
                    account.put("OpenDate",         rs.getDate("OPEN_DATE"));
                    accounts.add(account);
                }

                if (accounts.isEmpty()) return RC_NOT_FOUND;

                ctx.setValueAt("Accounts",          accounts);
                ctx.setValueAt("TotalAccountCount", String.valueOf(accounts.size()));
            }

        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }

        return RC_SUCCESS;
    }
}
