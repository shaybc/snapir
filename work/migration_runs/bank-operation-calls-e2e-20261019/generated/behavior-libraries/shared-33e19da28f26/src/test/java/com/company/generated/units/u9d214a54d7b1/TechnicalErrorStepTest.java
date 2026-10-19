package com.company.generated.units.u9d214a54d7b1;

import com.company.generated.units.u3a42c4326e3d.OperationContext;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class TechnicalErrorStepTest {

    @Test
    public void setsDefaultTechnicalErrorInContext() {
        OperationContext context = new OperationContext();
        TechnicalErrorStep step = new TechnicalErrorStep();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("99", context.getValueAt("ErrorCategory"));
        assertEquals("0", context.getValueAt("ErrorNumber"));
        assertEquals("Technical error: unexpected system failure", context.getValueAt("ErrorDescription"));
    }

    @Test
    public void setsCustomConfiguredErrorInContext() {
        OperationContext context = new OperationContext();
        TechnicalErrorStep step = new TechnicalErrorStep("40", "4");

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("40", context.getValueAt("ErrorCategory"));
        assertEquals("4", context.getValueAt("ErrorNumber"));
        assertEquals("Insufficient funds", context.getValueAt("ErrorDescription"));
        assertEquals("40", step.getErrorCategory());
        assertEquals("4", step.getErrorNumber());
    }
}
