package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;

/**
 * Executes a funds transfer between two accounts in the core banking database.
 *
 * Context reads: SourceAccount, TargetAccount, Amount, Currency, TransferReference,
 *                SessionToken, FraudScore
 * Context writes: TransferId, TransferStatus, ExecutionDate, ExecutionTime,
 *                 NewSourceBalance
 *
 * Returns:
 *   0 - transfer executed successfully
 *   6 - rejected by core banking (account rules, SWIFT, etc.)
 *   7 - duplicate transfer reference (already processed)
 *   8 - database error
 */
public class ExecuteTransferSP extends CCOperationStep {

    private static final String SP_NAME =
        "{call PKG_TRANSFERS.EXECUTE_TRANSFER(?,?,?,?,?,?,?,?,?,?)}";

    private static final int RC_SUCCESS   = 0;
    private static final int RC_REJECTED  = 6;
    private static final int RC_DUPLICATE = 7;
    private static final int RC_DB_ERROR  = 8;

    @Override
    public int execute() throws Exception {
        Context ctx = getContext();

        String     sourceAccount = (String)     ctx.getValueAt("SourceAccount");
        String     targetAccount = (String)     ctx.getValueAt("TargetAccount");
        BigDecimal amount        = (BigDecimal) ctx.getValueAt("Amount");
        String     currency      = (String)     ctx.getValueAt("Currency");
        String     reference     = (String)     ctx.getValueAt("TransferReference");

        Connection conn = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            // IN params
            cs.setString(    1, sourceAccount);
            cs.setString(    2, targetAccount);
            cs.setBigDecimal(3, amount);
            cs.setString(    4, currency != null ? currency.trim() : "ILS");
            cs.setString(    5, reference);

            // OUT params
            cs.registerOutParameter(6,  Types.VARCHAR);   // return code
            cs.registerOutParameter(7,  Types.VARCHAR);   // transfer id
            cs.registerOutParameter(8,  Types.VARCHAR);   // transfer status
            cs.registerOutParameter(9,  Types.DATE);      // execution date
            cs.registerOutParameter(10, Types.NUMERIC);   // new source balance

            cs.execute();

            String spRc = cs.getString(6);
            if ("REJECTED".equals(spRc))  return RC_REJECTED;
            if ("DUPLICATE".equals(spRc)) return RC_DUPLICATE;

            ctx.setValueAt("TransferId",       cs.getString(7));
            ctx.setValueAt("TransferStatus",   cs.getString(8));
            ctx.setValueAt("ExecutionDate",    cs.getDate(9));
            ctx.setValueAt("ExecutionTime",    new java.util.Date());
            ctx.setValueAt("NewSourceBalance", cs.getBigDecimal(10));

        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
        return RC_SUCCESS;
    }
}
