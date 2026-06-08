package com.ibm.il.dse.operations.ivr.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.*;

/**
 * Retrieves account balance for IVR channel. PIN-authenticated.
 *
 * Context reads: ClientId, AccountNumber, Pin
 * Context writes: AvailableBalance, BookBalance, Currency, BalanceDate
 *
 * Returns: 0=success, 4=not found, 8=db error
 */
public class GetAccountBalanceSP extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_IVR.GET_ACCOUNT_BALANCE(?,?,?,?,?)}";

    @Override
    public int execute() throws Exception {
        Context ctx    = getContext();
        String  clientId  = (String) ctx.getValueAt("ClientId");
        String  accountNo = (String) ctx.getValueAt("AccountNumber");
        String  pin       = (String) ctx.getValueAt("Pin");

        Connection conn = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, clientId);
            cs.setString(2, accountNo);
            cs.setString(3, pin);
            cs.registerOutParameter(4, Types.VARCHAR);
            cs.registerOutParameter(5, Types.REF_CURSOR);
            cs.execute();

            String spRc = cs.getString(4);
            if ("NOT_FOUND".equals(spRc)) return 4;

            try (ResultSet rs = (ResultSet) cs.getObject(5)) {
                if (rs.next()) {
                    ctx.setValueAt("AvailableBalance", rs.getBigDecimal("AVAILABLE_BALANCE"));
                    ctx.setValueAt("BookBalance",      rs.getBigDecimal("BOOK_BALANCE"));
                    ctx.setValueAt("Currency",         rs.getString("CURRENCY_CODE"));
                    ctx.setValueAt("BalanceDate",      rs.getDate("BALANCE_DATE"));
                }
            }
        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return 8;
        }
        return 0;
    }
}
