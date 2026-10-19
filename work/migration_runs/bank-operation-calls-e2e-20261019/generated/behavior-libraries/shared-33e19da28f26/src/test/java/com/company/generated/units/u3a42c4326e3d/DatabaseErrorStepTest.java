package com.company.generated.units.u3a42c4326e3d;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class DatabaseErrorStepTest {

    @Test
    public void executesDatabaseErrorMappingSuccessfully() {
        OperationContext context = new OperationContext();
        DatabaseErrorStep step = new DatabaseErrorStep();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("99", context.getValueAt("ErrorCategory"));
        assertEquals("8", context.getValueAt("ErrorNumber"));
        assertEquals("Technical error: database connection failure", context.getValueAt("ErrorDescription"));
    }

    @Test
    public void executesCustomErrorMappingSuccessfully() {
        OperationContext context = new OperationContext();
        DatabaseErrorStep step = new DatabaseErrorStep("10", "2");

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("10", context.getValueAt("ErrorCategory"));
        assertEquals("2", context.getValueAt("ErrorNumber"));
        assertEquals("Validation failed: required field missing or invalid", context.getValueAt("ErrorDescription"));
    }
}