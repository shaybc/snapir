package com.company.generated.units.u87dd336469df;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

public class InsufficientFundsStepTest {

    @Test
    public void executesAndSetsErrorDetailsInContext() {
        InsufficientFundsStep step = new InsufficientFundsStep();
        assertEquals("40", step.getErrorCategory());
        assertEquals("4", step.getErrorNumber());

        Map<String, Object> context = new HashMap<>();
        int rc = step.execute(context);

        assertEquals(0, rc);
        assertEquals("40", context.get("ErrorCategory"));
        assertEquals("4", context.get("ErrorNumber"));
        assertEquals("Insufficient funds", context.get("ErrorDescription"));
    }
}
