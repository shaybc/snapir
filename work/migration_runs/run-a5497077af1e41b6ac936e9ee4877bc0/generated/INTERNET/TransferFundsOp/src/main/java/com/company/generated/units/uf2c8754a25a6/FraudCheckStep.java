package com.company.generated.units.uf2c8754a25a6;

import com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort;
import java.math.BigDecimal;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.TimeoutException;

public class FraudCheckStep {
    private final int serviceTimeout;
    private final FraudDetectionServicePort fraudDetectionService;

    public FraudCheckStep(int serviceTimeout, FraudDetectionServicePort fraudDetectionService) {
        this.serviceTimeout = serviceTimeout;
        this.fraudDetectionService = Objects.requireNonNull(fraudDetectionService, "fraudDetectionService");
    }

    public int execute(Map<String, Object> context) throws Exception {
        Objects.requireNonNull(context, "context");
        String sourceAccount = (String) context.get("SourceAccount");
        String targetAccount = (String) context.get("TargetAccount");
        BigDecimal amount = (BigDecimal) context.get("Amount");
        String clientId = (String) context.get("ClientId");

        String requestPayload = buildFraudRequest(clientId, sourceAccount, targetAccount, amount);

        String response;
        try {
            response = fraudDetectionService.call(requestPayload, serviceTimeout);
        } catch (TimeoutException e) {
            return -99;
        } catch (Exception e) {
            context.put("ServiceError", e.getMessage());
            return 8;
        }

        int fraudScore = parseFraudScore(response);
        String decision = parseFraudDecision(response);

        context.put("FraudScore", fraudScore);
        context.put("FraudDecision", decision);

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
        int start = response.indexOf("<Score>") + 7;
        int end = response.indexOf("</Score>");
        if (start > 6 && end > start) {
            return Integer.parseInt(response.substring(start, end));
        }
        return 0;
    }

    private String parseFraudDecision(String response) {
        return response.contains("<Decision>BLOCK</Decision>") ? "BLOCK" : "ALLOW";
    }
}
