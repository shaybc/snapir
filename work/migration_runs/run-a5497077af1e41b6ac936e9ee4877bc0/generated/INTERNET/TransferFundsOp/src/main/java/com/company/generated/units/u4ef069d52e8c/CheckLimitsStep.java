package com.company.generated.units.u4ef069d52e8c;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;
import java.util.Map;
import java.util.Objects;

public class CheckLimitsStep {
    private static final String SP_NAME = "{call PKG_TRANSFERS.VALIDATE_LIMITS(?,?,?,?,?,?)}";

    private static final int RC_SUCCESS = 0;
    private static final int RC_LIMIT_EXCEEDED = 3;
    private static final int RC_INSUFFICIENT = 4;
    private static final int RC_NOT_ELIGIBLE = 5;
    private static final int RC_DB_ERROR = 8;

    public int execute(Map<String, Object> context) {
        Objects.requireNonNull(context, "Context cannot be null");
        String sourceAccount = (String) context.get("SourceAccount");
        BigDecimal amount = (BigDecimal) context.get("Amount");
        String clientId = (String) context.get("ClientId");

        Connection conn = (Connection) context.get("Connection");
        if (conn == null) {
            throw new IllegalStateException("Configure a JDBC connection before executing a database step");
        }

        try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
            cs.setString(1, sourceAccount);
            cs.setBigDecimal(2, amount);
            cs.setString(3, clientId);

            cs.registerOutParameter(4, Types.VARCHAR);
            cs.registerOutParameter(5, Types.NUMERIC);
            cs.registerOutParameter(6, Types.NUMERIC);

            cs.execute();

            String spRc = cs.getString(4);
            if (spRc == null) {
                spRc = "SUCCESS";
            }
            switch (spRc) {
                case "LIMIT_EXCEEDED":
                    context.put("DailyRemaining", cs.getBigDecimal(5));
                    context.put("DailyLimit", cs.getBigDecimal(6));
                    return RC_LIMIT_EXCEEDED;
                case "INSUFFICIENT":
                    return RC_INSUFFICIENT;
                case "NOT_ELIGIBLE":
                    return RC_NOT_ELIGIBLE;
                default:
                    return RC_SUCCESS;
            }
        } catch (Exception e) {
            context.put("DatabaseError", e.getMessage());
            return RC_DB_ERROR;
        }
    }
}
