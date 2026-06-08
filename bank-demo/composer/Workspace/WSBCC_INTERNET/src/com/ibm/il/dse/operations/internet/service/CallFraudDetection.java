package com.ibm.il.dse.operations.internet.service;

import com.ibm.dse.base.CCOperationStep;
import com.ibm.dse.base.Context;
import com.ibm.il.dse.cc.service.communication.http.HTTPService;

import java.math.BigDecimal;

/**
 * Calls the fraud detection backend service via HTTP.
 * This opStep has a configurable timeout (ServiceTimeout attribute).
 *
 * XML attributes:
 *   ServiceTimeout - milliseconds before onTimeoutDo fires (default 5000)
 *
 * Context reads: SourceAccount, TargetAccount, Amount, Currency, ClientId
 * Context writes: FraudScore (int 0-100), FraudDecision (ALLOW/BLOCK)
 *
 * Returns:
 *   0 - fraud check passed (ALLOW decision)
 *   2 - fraud suspected (BLOCK decision, score >= threshold)
 *  -99 - timeout (handled by onTimeoutDo routing)
 *   8 - service error
 */
public class CallFraudDetection extends CCOperationStep {

    private int serviceTimeout = 5000;

    public void setServiceTimeout(String timeout) {
        this.serviceTimeout = Integer.parseInt(timeout);
    }

    @Override
    public int execute() throws Exception {
        Context    ctx           = getContext();
        String     sourceAccount = (String)     ctx.getValueAt("SourceAccount");
        String     targetAccount = (String)     ctx.getValueAt("TargetAccount");
        BigDecimal amount        = (BigDecimal) ctx.getValueAt("Amount");
        String     clientId      = (String)     ctx.getValueAt("ClientId");

        // Build fraud check request payload
        String requestPayload = buildFraudRequest(clientId, sourceAccount, targetAccount, amount);

        // Call fraud service via HTTPService
        HTTPService httpService = (HTTPService) getService("FraudDetectionService");
        String response;
        try {
            response = httpService.call(requestPayload, serviceTimeout);
        } catch (java.util.concurrent.TimeoutException e) {
            return -99; // timeout -> onTimeoutDo routing
        } catch (Exception e) {
            ctx.setValueAt("ServiceError", e.getMessage());
            return 8;
        }

        // Parse response
        int fraudScore = parseFraudScore(response);
        String decision = parseFraudDecision(response);

        ctx.setValueAt("FraudScore",    fraudScore);
        ctx.setValueAt("FraudDecision", decision);

        // Score >= 70 is considered fraud
        return "BLOCK".equals(decision) ? 2 : 0;
    }

    private String buildFraudRequest(String clientId, String src, String tgt, BigDecimal amt) {
        return "<FraudCheckRequest>"
            + "<ClientId>" + clientId + "</ClientId>"
            + "<SourceAccount>" + src + "</SourceAccount>"
            + "<TargetAccount>" + tgt + "</TargetAccount>"
            + "<Amount>" + amt + "</Amount>"
            + "</FraudCheckRequest>";
    }

    private int parseFraudScore(String response) {
        // Simplified parser for demo
        int start = response.indexOf("<Score>") + 7;
        int end   = response.indexOf("</Score>");
        if (start > 6 && end > start) {
            return Integer.parseInt(response.substring(start, end));
        }
        return 0;
    }

    private String parseFraudDecision(String response) {
        return response.contains("<Decision>BLOCK</Decision>") ? "BLOCK" : "ALLOW";
    }
}
