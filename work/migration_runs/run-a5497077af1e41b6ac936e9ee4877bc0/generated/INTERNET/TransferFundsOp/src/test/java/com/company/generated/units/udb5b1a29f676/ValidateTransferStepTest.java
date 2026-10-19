package com.company.generated.units.udb5b1a29f676;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class ValidateTransferStepTest {

    @Test
    public void testAllRequiredFieldsPresent() {
        ValidateTransferStep step = new ValidateTransferStep();
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "12345");
        context.put("TargetAccount", "67890");
        context.put("Amount", "100.00");
        context.put("Currency", "USD");
        context.put("SessionToken", "token-abc");

        int rc = step.execute(context);
        assertEquals(0, rc);
    }

    @Test
    public void testMissingRequiredField() {
        ValidateTransferStep step = new ValidateTransferStep();
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "12345");
        // TargetAccount is missing
        context.put("Amount", "100.00");
        context.put("Currency", "USD");
        context.put("SessionToken", "token-abc");

        int rc = step.execute(context);
        assertEquals(1, rc);
        assertEquals("TargetAccount", context.get("ValidationFailedField"));
    }

    @Test
    public void testBlankRequiredField() {
        ValidateTransferStep step = new ValidateTransferStep();
        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "12345");
        context.put("TargetAccount", "   ");
        context.put("Amount", "100.00");
        context.put("Currency", "USD");
        context.put("SessionToken", "token-abc");

        int rc = step.execute(context);
        assertEquals(1, rc);
        assertEquals("TargetAccount", context.get("ValidationFailedField"));
    }
}
