package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;

/**
 * Fetches detailed account information for a specific account.
 *
 * Context reads: ClientId, AccountNumber, BankId
 * Context writes: AccountHolderName, AccountTypeCode, BranchCode, BranchName,
 *                 OpenDate, LastActivityDate, AvailableBalance, BookBalance,
 *                 HoldAmount, Currency
 *
 * Returns:
 *   0 - account found and details loaded
 *   4 - account not found
 *   5 - client does not have access to this account
 *   8 - database error
 */
public class GetAccountDetailsSP extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_ACCOUNTS.GET_ACCOUNT_DETAILS(?,?,?,?,?)}";
    private static final int RC_SUCCESS      = 0;
    private static final int RC_NOT_FOUND    = 4;
    private static final int RC_ACCESS_DENIED = 5;
    private static final int RC_DB_ERROR     = 8;

    @Override
    public int execute() throws Exception {
        Context ctx = getContext();
        String clientId      = (String) ctx.getValueAt("ClientId");
        String accountNumber = (String) ctx.getValueAt("AccountNumber");

        Connection conn = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, clientId);
            cs.setString(2, accountNumber);
            cs.registerOutParameter(3, Types.VARCHAR);   // return code
            cs.registerOutParameter(4, Types.REF_CURSOR); // account detail row
            cs.registerOutParameter(5, Types.REF_CURSOR); // balance details

            cs.execute();

            String spRc = cs.getString(3);
            if ("NOT_FOUND".equals(spRc))     return RC_NOT_FOUND;
            if ("ACCESS_DENIED".equals(spRc)) return RC_ACCESS_DENIED;

            try (java.sql.ResultSet rs = (java.sql.ResultSet) cs.getObject(4)) {
                if (rs.next()) {
                    ctx.setValueAt("AccountHolderName", rs.getString("HOLDER_NAME"));
                    ctx.setValueAt("AccountTypeCode",   rs.getString("ACCOUNT_TYPE_CODE"));
                    ctx.setValueAt("BranchCode",        rs.getString("BRANCH_CODE"));
                    ctx.setValueAt("BranchName",        rs.getString("BRANCH_NAME"));
                    ctx.setValueAt("OpenDate",          rs.getDate("OPEN_DATE"));
                    ctx.setValueAt("LastActivityDate",  rs.getDate("LAST_ACTIVITY_DATE"));
                    ctx.setValueAt("Currency",          rs.getString("CURRENCY_CODE"));
                }
            }
            try (java.sql.ResultSet bs = (java.sql.ResultSet) cs.getObject(5)) {
                if (bs.next()) {
                    ctx.setValueAt("AvailableBalance", bs.getBigDecimal("AVAILABLE_BALANCE"));
                    ctx.setValueAt("BookBalance",      bs.getBigDecimal("BOOK_BALANCE"));
                    ctx.setValueAt("HoldAmount",       bs.getBigDecimal("HOLD_AMOUNT"));
                }
            }

        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
        return RC_SUCCESS;
    }
}
