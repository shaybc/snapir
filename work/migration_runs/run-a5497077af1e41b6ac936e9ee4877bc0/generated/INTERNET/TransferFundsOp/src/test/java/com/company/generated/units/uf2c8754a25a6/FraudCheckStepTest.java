package com.company.generated.units.uf2c8754a25a6;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeoutException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class FraudCheckStepTest {

    @Test
    public void executesAllowDecisionSuccessfully() throws Exception {
        FraudDetectionServicePort service = mock(FraudDetectionServicePort.class);
        when(service.call(anyString(), eq(5000)))
                .thenReturn("<FraudResponse><Score>10</Score><Decision>ALLOW</Decision></FraudResponse>");

        FraudCheckStep step = new FraudCheckStep(5000, service);
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("150.00"));
        context.put("ClientId", "CLI-999");

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals(10, context.get("FraudScore"));
        assertEquals("ALLOW", context.get("FraudDecision"));
        verify(service).call(anyString(), eq(5000));
    }

    @Test
    public void executesBlockDecisionWhenSusppected() throws Exception {
        FraudDetectionServicePort service = mock(FraudDetectionServicePort.class);
        when(service.call(anyString(), eq(5000)))
                .thenReturn("<FraudResponse><Score>85</Score><Decision>BLOCK</Decision></FraudResponse>");

        FraudCheckStep step = new FraudCheckStep(5000, service);
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("5000.00"));
        context.put("ClientId", "CLI-999");

        int result = step.execute(context);

        assertEquals(2, result);
        assertEquals(85, context.get("FraudScore"));
        assertEquals("BLOCK", context.get("FraudDecision"));
    }

    @Test
    public void handlesTimeoutException() throws Exception {
        FraudDetectionServicePort service = mock(FraudDetectionServicePort.class);
        when(service.call(anyString(), eq(5000))).thenThrow(new TimeoutException("Timed out"));

        FraudCheckStep step = new FraudCheckStep(5000, service);
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("100.00"));
        context.put("ClientId", "CLI-999");

        int result = step.execute(context);

        assertEquals(-99, result);
    }

    @Test
    public void handlesTechnicalException() throws Exception {
        FraudDetectionServicePort service = mock(FraudDetectionServicePort.class);
        when(service.call(anyString(), eq(5000))).thenThrow(new RuntimeException("Network error"));

        FraudCheckStep step = new FraudCheckStep(5000, service);
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("100.00"));
        context.put("ClientId", "CLI-999");

        int result = step.execute(context);

        assertEquals(8, result);
        assertEquals("Network error", context.get("ServiceError"));
    }
}
