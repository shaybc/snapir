package il.co.dcd.verification.fixtures;

import java.util.List;
import java.util.Map;

/** Observations from a JUnit scenario; setup failures never become business exceptions. */
public record FixtureResult(Object value, Throwable exception, List<Map<String, Object>> events, List<Object> arguments, Object receiver) {
    public FixtureResult(Object value, Throwable exception, List<Map<String,Object>> events, List<Object> arguments) {
        this(value,exception,events,arguments,null);
    }
}
