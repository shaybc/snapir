package com.company.generated.units.u9d214a54d7b1;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class TechnicalErrorStepTest {

    @Test
    public void populatesDefaultTechnicalErrorIntoContext() {
        TechnicalErrorStep step = new TechnicalErrorStep();
        Map<String, Object> context = new HashMap<>();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("99", context.get("ErrorCategory"));
        assertEquals("0", context.get("ErrorNumber"));
        assertEquals("Technical error: unexpected system failure", context.get("ErrorDescription"));
    }

    @Test
    public void populatesCustomErrorIntoContext() {
        TechnicalErrorStep step = new TechnicalErrorStep("10", "2");
        Map<String, Object> context = new HashMap<>();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("10", context.get("ErrorCategory"));
        assertEquals("2", context.get("ErrorNumber"));
        assertEquals("Validation failed: required field missing or invalid", context.get("ErrorDescription"));
    }
}
