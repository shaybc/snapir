package com.company.generated.units.u1e4c733765f0;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class AccountNotEligibleStepTest {

    @Test
    public void testExecuteAccountNotEligible() {
        AccountNotEligibleStep step = new AccountNotEligibleStep();
        Map<String, Object> context = new HashMap<>();
        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("40", context.get("ErrorCategory"));
        assertEquals("5", context.get("ErrorNumber"));
        assertEquals("Account not eligible for this operation", context.get("ErrorDescription"));
        assertEquals("40", step.getErrorCategory());
        assertEquals("5", step.getErrorNumber());
    }
}
