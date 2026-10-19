package com.company.generated.units.u1bde9d232fc4;

import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class DailyLimitExceededStepTest {

    @Test
    public void setsDailyLimitExceededErrorInContext() {
        DailyLimitExceededStep step = new DailyLimitExceededStep();
        Map<String, Object> context = new HashMap<>();

        int rc = step.execute(context);

        assertEquals(0, rc);
        assertEquals("40", context.get("ErrorCategory"));
        assertEquals("3", context.get("ErrorNumber"));
        assertEquals("Daily transfer limit exceeded", context.get("ErrorDescription"));
    }
}
