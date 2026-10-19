package com.company.generated.units.u2e52a65fe1ce;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class ValidationFailedStepTest {

    @Test
    public void testValidationFailedStepExecution() {
        Map<String, Object> context = new HashMap<>();
        ValidationFailedStep step = new ValidationFailedStep();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("10", context.get("ErrorCategory"));
        assertEquals("2", context.get("ErrorNumber"));
        assertEquals("Validation failed: required field missing or invalid", context.get("ErrorDescription"));
    }
}