package com.company.generated.units.u3643d2141e0a;

import com.company.generated.units.u3a42c4326e3d.OperationContext;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class NoLinksFoundStepBusinessTest {
    @Test
    public void setsErrorCategoryAndDescriptionForNoLinksFound() {
        OperationContext context = new OperationContext();
        NoLinksFoundStep step = new NoLinksFoundStep();
        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("20", context.getValueAt("ErrorCategory"));
        assertEquals("1", context.getValueAt("ErrorNumber"));
        assertEquals("No data found for the provided criteria", context.getValueAt("ErrorDescription"));
    }
}
