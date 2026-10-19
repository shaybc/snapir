package com.company.generated.units.u06cdcaacb2a8;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class CoreBankingRejectedStepBusinessTest {

    @Test
    public void populatesCoreBankingRejectedErrorDetails() {
        CoreBankingRejectedStep step = new CoreBankingRejectedStep();
        Map<String, Object> context = new HashMap<>();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("60", context.get("ErrorCategory"));
        assertEquals("6", context.get("ErrorNumber"));
        assertEquals("Core banking system rejected the request", context.get("ErrorDescription"));
        assertEquals("60", step.getErrorCategory());
        assertEquals("6", step.getErrorNumber());
    }
}
