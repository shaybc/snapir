package com.company.generated.units.u3edad4d894ed;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

public class SkipFraudOnTimeoutStepTest {

    @Test
    public void setsConfiguredContextFieldSuccessfully() {
        SkipFraudOnTimeoutStep step = new SkipFraudOnTimeoutStep();
        assertEquals("FraudCheckSkipped", step.getFieldName());
        assertEquals("true", step.getFieldValue());

        Map<String, Object> context = new HashMap<>();
        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("true", context.get("FraudCheckSkipped"));
    }

    @Test
    public void handlesCustomConstructorValues() {
        SkipFraudOnTimeoutStep step = new SkipFraudOnTimeoutStep("CustomField", "false");
        assertEquals("CustomField", step.getFieldName());
        assertEquals("false", step.getFieldValue());

        Map<String, Object> context = new HashMap<>();
        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("false", context.get("CustomField"));
    }
}
