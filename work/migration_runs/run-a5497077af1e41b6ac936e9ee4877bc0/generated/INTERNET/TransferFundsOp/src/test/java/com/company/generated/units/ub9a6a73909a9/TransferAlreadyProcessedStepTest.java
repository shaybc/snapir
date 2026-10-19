package com.company.generated.units.ub9a6a73909a9;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class TransferAlreadyProcessedStepTest {

    @Test
    public void setsTransferAlreadyProcessedErrorAndReturnsZero() {
        TransferAlreadyProcessedStep step = new TransferAlreadyProcessedStep();
        assertEquals("60", step.getErrorCategory());
        assertEquals("7", step.getErrorNumber());

        Map<String, Object> context = new HashMap<>();
        int rc = step.execute(context);

        assertEquals(0, rc);
        assertEquals("60", context.get("ErrorCategory"));
        assertEquals("7", context.get("ErrorNumber"));
        assertEquals("Transfer already processed", context.get("ErrorDescription"));
    }
}
