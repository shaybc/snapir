package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.*;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Fetches account transaction history for a date range.
 * Called as second step in GetAccountDetailsOp.
 *
 * Context reads: AccountNumber, FromDate, ToDate, MaxTransactions
 * Context writes: Transactions (List of Map), TransactionCount
 *
 * Returns:
 *   0 - transactions fetched (may be empty list — not an error)
 *   4 - empty result (no transactions in range)
 *   8 - database error
 */
public class GetAccountTransactionsSP extends CCOperationStep {

    private static final String SP_NAME =
        "{call PKG_ACCOUNTS.GET_ACCOUNT_TRANSACTIONS(?,?,?,?,?,?)}";

    private static final int RC_SUCCESS   = 0;
    private static final int RC_EMPTY     = 4;
    private static final int RC_DB_ERROR  = 8;

    @Override
    public int execute() throws Exception {
        Context ctx           = getContext();
        String  accountNumber = (String)  ctx.getValueAt("AccountNumber");
        Object  fromDateObj   = ctx.getValueAt("FromDate");
        Object  toDateObj     = ctx.getValueAt("ToDate");
        String  maxTxStr      = (String)  ctx.getValueAt("MaxTransactions");
        int     maxTx         = (maxTxStr != null && !maxTxStr.isBlank())
                                ? Integer.parseInt(maxTxStr) : 50;

        Connection conn = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, accountNumber);
            cs.setDate(  2, fromDateObj != null
                            ? new java.sql.Date(((java.util.Date) fromDateObj).getTime()) : null);
            cs.setDate(  3, toDateObj != null
                            ? new java.sql.Date(((java.util.Date) toDateObj).getTime()) : null);
            cs.setInt(   4, maxTx);
            cs.registerOutParameter(5, Types.VARCHAR);
            cs.registerOutParameter(6, Types.REF_CURSOR);
            cs.execute();

            String spRc = cs.getString(5);
            if ("EMPTY".equals(spRc)) {
                ctx.setValueAt("Transactions",    new ArrayList<>());
                ctx.setValueAt("TransactionCount", "0");
                return RC_EMPTY;
            }

            try (ResultSet rs = (ResultSet) cs.getObject(6)) {
                List<Map<String, Object>> txns = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> tx = new LinkedHashMap<>();
                    tx.put("TransactionId",       rs.getString("TXN_ID"));
                    tx.put("TransactionDate",      rs.getDate("TXN_DATE"));
                    tx.put("TransactionTime",      rs.getString("TXN_TIME"));
                    tx.put("Description",          rs.getString("DESCRIPTION"));
                    tx.put("Amount",               rs.getBigDecimal("AMOUNT"));
                    tx.put("DebitCredit",          rs.getString("DR_CR_IND"));
                    tx.put("BalanceAfter",         rs.getString("BALANCE_AFTER"));
                    tx.put("TransactionTypeCode",  rs.getString("TXN_TYPE_CODE"));
                    txns.add(tx);
                }
                ctx.setValueAt("Transactions",     txns);
                ctx.setValueAt("TransactionCount", String.valueOf(txns.size()));
            }
        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
        return RC_SUCCESS;
    }
}
