package com.company.generated.units.u6d24746bc47a;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;
import java.util.Map;
import java.util.Objects;

public class ExecuteTransferStep {

    private static final String SP_NAME =
        "{call PKG_TRANSFERS.EXECUTE_TRANSFER(?,?,?,?,?,?,?,?,?,?)}";

    public static final int RC_SUCCESS   = 0;
    public static final int RC_REJECTED  = 6;
    public static final int RC_DUPLICATE = 7;
    public static final int RC_DB_ERROR  = 8;

    public int execute(Map<String, Object> context) {
        Map<String, Object> ctx = Objects.requireNonNull(context, "Context map");

        String     sourceAccount = (String)     ctx.get("SourceAccount");
        String     targetAccount = (String)     ctx.get("TargetAccount");
        BigDecimal amount        = (BigDecimal) ctx.get("Amount");
        String     currency      = (String)     ctx.get("Currency");
        String     reference     = (String)     ctx.get("TransferReference");

        Connection conn = (Connection) ctx.get("Connection");
        if (conn == null) {
            throw new IllegalStateException("Configure a JDBC connection before executing a database step");
        }

        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(    1, sourceAccount);
            cs.setString(    2, targetAccount);
            cs.setBigDecimal(3, amount);
            cs.setString(    4, currency != null ? currency.trim() : "ILS");
            cs.setString(    5, reference);

            cs.registerOutParameter(6,  Types.VARCHAR);
            cs.registerOutParameter(7,  Types.VARCHAR);
            cs.registerOutParameter(8,  Types.VARCHAR);
            cs.registerOutParameter(9,  Types.DATE);
            cs.registerOutParameter(10, Types.NUMERIC);

            cs.execute();

            String spRc = cs.getString(6);
            if ("REJECTED".equals(spRc))  return RC_REJECTED;
            if ("DUPLICATE".equals(spRc)) return RC_DUPLICATE;

            ctx.put("TransferId",       cs.getString(7));
            ctx.put("TransferStatus",   cs.getString(8));
            ctx.put("ExecutionDate",    cs.getDate(9));
            ctx.put("ExecutionTime",    new java.util.Date());
            ctx.put("NewSourceBalance", cs.getBigDecimal(10));

        } catch (Exception e) {
            ctx.put("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
        return RC_SUCCESS;
    }
}
