package com.company.generated.units.u3a42c4326e3d;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class MapErrorByValueAlwaysTest {

    @Test
    public void executesAndSetsConfiguredDatabaseError() {
        Map<String, Object> context = new HashMap<>();
        MapErrorByValueAlways step = new MapErrorByValueAlways();

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("99", context.get("ErrorCategory"));
        assertEquals("8", context.get("ErrorNumber"));
        assertEquals("Technical error: database connection failure", context.get("ErrorDescription"));
    }

    @Test
    public void executesWithCustomErrorValues() {
        Map<String, Object> context = new HashMap<>();
        MapErrorByValueAlways step = new MapErrorByValueAlways();
        step.setErrorCategory("10");
        step.setErrorNumber("2");

        int result = step.execute(context);

        assertEquals(0, result);
        assertEquals("10", context.get("ErrorCategory"));
        assertEquals("2", context.get("ErrorNumber"));
        assertEquals("Validation failed: required field missing or invalid", context.get("ErrorDescription"));
    }
}