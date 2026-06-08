package com.ibm.il.dse.operations.internet.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;

/**
 * Validates that a transfer does not exceed account limits.
 * Checks: daily limit, available balance, account eligibility.
 *
 * Context reads: SourceAccount, Amount, Currency, ClientId
 * Context writes: DailyRemaining, DailyLimit (on limit exceeded case)
 *
 * Returns:
 *   0 - transfer is within limits and account is eligible
 *   3 - daily transfer limit would be exceeded
 *   4 - insufficient available funds
 *   5 - source account not eligible for outgoing transfers
 *   8 - database error
 */
public class ValidateTransferLimitsSP extends CCOperationStep {

    private static final String SP_NAME =
        "{call PKG_TRANSFERS.VALIDATE_LIMITS(?,?,?,?,?,?)}";

    private static final int RC_SUCCESS         = 0;
    private static final int RC_LIMIT_EXCEEDED  = 3;
    private static final int RC_INSUFFICIENT    = 4;
    private static final int RC_NOT_ELIGIBLE    = 5;
    private static final int RC_DB_ERROR        = 8;

    @Override
    public int execute() throws Exception {
        Context    ctx           = getContext();
        String     sourceAccount = (String)     ctx.getValueAt("SourceAccount");
        BigDecimal amount        = (BigDecimal) ctx.getValueAt("Amount");
        String     clientId      = (String)     ctx.getValueAt("ClientId");

        Connection conn = ctx.getConnection();
        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(    1, sourceAccount);
            cs.setBigDecimal(2, amount);
            cs.setString(    3, clientId);

            cs.registerOutParameter(4, Types.VARCHAR);   // validation result code
            cs.registerOutParameter(5, Types.NUMERIC);   // daily remaining
            cs.registerOutParameter(6, Types.NUMERIC);   // daily limit

            cs.execute();

            String spRc = cs.getString(4);
            switch (spRc) {
                case "LIMIT_EXCEEDED":
                    ctx.setValueAt("DailyRemaining", cs.getBigDecimal(5));
                    ctx.setValueAt("DailyLimit",     cs.getBigDecimal(6));
                    return RC_LIMIT_EXCEEDED;
                case "INSUFFICIENT":
                    return RC_INSUFFICIENT;
                case "NOT_ELIGIBLE":
                    return RC_NOT_ELIGIBLE;
                default:
                    return RC_SUCCESS;
            }
        } catch (Exception e) {
            ctx.setValueAt("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
    }
}
