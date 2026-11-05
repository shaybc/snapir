package il.co.dcd.integration;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.List;
import org.springframework.core.io.DefaultResourceLoader;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class OperationContextFactoryTest {
    @TempDir Path directory;
    @Test void preservesCasingAndDoesNotShareNestedRequestState() throws Exception {
        Path file = directory.resolve("initial.json");
        Files.writeString(file, "{\"Channel\":\"INTERNET\",\"Nested\":{\"Items\":[\"first\"]}}");
        NativeRuntimeProperties properties = new NativeRuntimeProperties(); properties.setInitializationFile(file.toUri().toString());
        OperationContextFactory factory = new OperationContextFactory(new DefaultResourceLoader(), properties);
        Map<String,Object> first = factory.create(), second = factory.create();
        assertEquals("INTERNET", first.get("Channel")); assertFalse(first.containsKey("channel"));
        ((List<Object>)((Map<?,?>)first.get("Nested")).get("Items")).add("changed");
        assertEquals(1, ((List<?>)((Map<?,?>)second.get("Nested")).get("Items")).size());
    }
}
