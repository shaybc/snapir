package com.company.generated.units.u3a42c4326e3d;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class DatabaseErrorBusinessTest {

    @Test
    public void setsErrorCategoryNumberAndDescriptionIntoContext() {
        Map<String, Object> context = new HashMap<>();
        DatabaseErrorStep step = new DatabaseErrorStep();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("99", context.get("ErrorCategory"));
        assertEquals("8", context.get("ErrorNumber"));
        assertEquals("Technical error: database connection failure", context.get("ErrorDescription"));
    }
}
