package com.company.generated.units.u90e3461e522a;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class FraudSuspectedStepTest {

    @Test
    public void executesSuccessfullyAndPopulatesContext() {
        FraudSuspectedStep step = new FraudSuspectedStep();
        Map<String, Object> context = new HashMap<>();

        int rc = step.execute(context);

        assertEquals(0, rc);
        assertEquals("50", context.get("ErrorCategory"));
        assertEquals("2", context.get("ErrorNumber"));
        assertEquals("Transfer blocked: fraud risk detected", context.get("ErrorDescription"));
    }

    @Test
    public void exposesCorrectErrorMetadata() {
        FraudSuspectedStep step = new FraudSuspectedStep();
        assertEquals("50", step.getErrorCategory());
        assertEquals("2", step.getErrorNumber());
    }
}
