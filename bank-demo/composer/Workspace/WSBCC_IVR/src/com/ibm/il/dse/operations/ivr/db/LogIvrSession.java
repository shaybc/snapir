package com.ibm.il.dse.operations.ivr.db;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.util.Date;

/**
 * IVR-only logging opStep. Records IVR session activity for compliance.
 * This step is tagged onlyFor="IVR" in operation XMLs and is invisible
 * to all other channels.
 *
 * Context reads: ClientId, CHANNEL_ID, (operation name from session)
 * Context writes: IvrSessionId (string)
 *
 * Returns: 0 always (logging failure does not block the operation)
 */
public class LogIvrSession extends CCOperationStep {

    private static final String SP_NAME = "{call PKG_IVR.LOG_SESSION(?,?,?,?)}";

    @Override
    public int execute() {
        Context ctx = getContext();
        String  clientId  = (String) ctx.getValueAt("ClientId");
        String  channelId = (String) ctx.getValueAt("CHANNEL_ID");

        try {
            Connection conn = ctx.getConnection();
            try (CallableStatement cs = conn.prepareCall(SP_NAME)) {
                cs.setString(1, clientId);
                cs.setString(2, channelId != null ? channelId : "IVR");
                cs.setTimestamp(3, new java.sql.Timestamp(new Date().getTime()));
                cs.registerOutParameter(4, java.sql.Types.VARCHAR); // session id
                cs.execute();
                ctx.setValueAt("IvrSessionId", cs.getString(4));
            }
        } catch (Exception e) {
            // Logging failure is non-fatal — always return 0
        }
        return 0;
    }
}
