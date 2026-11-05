package il.co.dcd.integration;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import org.springframework.core.io.ResourceLoader;

/** Loads exact-case initialization once and deep-copies mutable values for each invocation. */
public final class OperationContextFactory {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, Object> initial;
    public OperationContextFactory(ResourceLoader loader, NativeRuntimeProperties properties) throws IOException {
        try (InputStream input = loader.getResource(properties.getInitializationFile()).getInputStream()) {
            initial = mapper.readValue(input, new TypeReference<Map<String, Object>>() { });
        }
    }
    public Map<String, Object> create() {
        return mapper.convertValue(initial, new TypeReference<Map<String, Object>>() { });
    }
}
