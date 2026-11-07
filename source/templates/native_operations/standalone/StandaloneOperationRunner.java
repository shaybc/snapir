// Generic standalone XML launcher. Generated operation code is loaded unchanged.
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.util.HashSet;
import java.util.Set;
import javax.sql.DataSource;

public final class StandaloneOperationRunner {
    private Connection connection;
    private RuntimeDatabase database;
    private JsonNode serviceUrls;

    public static void main(String[] args) {
        PrintStream response = System.out;
        System.setOut(System.err);
        StandaloneOperationRunner runner = new StandaloneOperationRunner();
        int status = 0;
        try { runner.run(args, response); }
        catch (Exception error) {
            // Driver exceptions can contain URLs/credentials. Do not echo their messages.
            System.err.println("Standalone operation failed (" + error.getClass().getSimpleName()
                    + "). Check the configuration, JDBC driver, request and entry signature.");
            status = 1;
        } finally {
            if (runner.connection != null) {
                try { runner.connection.close(); }
                catch (Exception error) { System.err.println("Database connection close failed."); status = 1; }
            }
        }
        if (status != 0) System.exit(status);
    }

    private void run(String[] args, PrintStream response) throws Exception {
        if (args.length < 2 || args[1].equals("--help")) {
            System.err.println("Usage: run-operation.bat <request.xml|-> [--config path] [--database name]");
            if (args.length < 2) throw new IllegalArgumentException("Missing XML request");
            return;
        }
        Path bindingPath = Path.of(args[0]).toAbsolutePath();
        ObjectMapper mapper = new ObjectMapper();
        JsonNode binding = mapper.readTree(bindingPath.toFile());
        Path config = bindingPath.getParent().resolve(binding.path("runtime_config").asText()).normalize();
        String databaseName = binding.path("database").asText("default");
        for (int i = 2; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing option value");
            switch (args[i]) {
                case "--config": config = Path.of(args[i + 1]); break;
                case "--database": databaseName = args[i + 1]; break;
                default: throw new IllegalArgumentException("Unknown option");
            }
        }
        JsonNode runtime = mapper.readTree(config.toFile());
        database = new RuntimeDatabase(runtime, databaseName);
        serviceUrls = runtime.path("service_urls");
        String xml = args[1].equals("-")
                ? new String(System.in.readAllBytes(), StandardCharsets.UTF_8)
                : Files.readString(Path.of(args[1]), StandardCharsets.UTF_8);
        Class<?> service = Class.forName(binding.path("service_class").asText());
        Method entry = entryMethod(service);
        Object instance = construct(service, new HashSet<>());
        Object[] values = new Object[entry.getParameterCount()];
        values[0] = xml;
        for (int i = 1; i < values.length; i++) values[i] = resource(entry.getParameterTypes()[i]);
        Object result;
        try { result = entry.invoke(instance, values); }
        catch (InvocationTargetException error) { throw new Exception(error.getCause()); }
        if (!(result instanceof String)) throw new IllegalStateException("XML response must be a String");
        response.print((String) result);
    }

    private static Method entryMethod(Class<?> service) throws NoSuchMethodException {
        // Prefer the JDBC entry over the no-connection convenience overload.
        for (String name : new String[]{"execute", "process"}) {
            for (Class<?>[] parameters : new Class<?>[][]{
                    {String.class, Connection.class}, {String.class, DataSource.class}, {String.class}}) {
                try {
                    Method method = service.getMethod(name, parameters);
                    if (method.getReturnType() == String.class) return method;
                } catch (NoSuchMethodException ignored) { }
            }
        }
        throw new NoSuchMethodException("Requires an XML String execute/process entry");
    }

    private Object resource(Class<?> type) throws Exception {
        if (type == DataSource.class) return database;
        if (type == Connection.class) {
            if (connection == null) connection = database.getConnection();
            return connection;
        }
        throw new IllegalArgumentException("Unsupported runtime resource type");
    }

    private Object construct(Class<?> type, Set<Class<?>> constructing) throws Exception {
        if (type == Connection.class || type == DataSource.class) return resource(type);
        if (!constructing.add(type)) throw new IllegalArgumentException("Cyclic constructor dependencies");
        try {
            try { return type.getConstructor().newInstance(); }
            catch (NoSuchMethodException ignored) { }
            Constructor<?>[] constructors = type.getConstructors();
            if (constructors.length != 1)
                throw new IllegalArgumentException("Constructor selection is ambiguous for " + type.getName());
            Constructor<?> constructor = constructors[0];
            Object[] arguments = new Object[constructor.getParameterCount()];
            java.beans.ConstructorProperties properties = constructor.getAnnotation(java.beans.ConstructorProperties.class);
            if (properties != null && properties.value().length != arguments.length)
                throw new IllegalArgumentException("Constructor property binding count differs");
            for (int i = 0; i < arguments.length; i++) {
                String property = properties == null ? "" : properties.value()[i];
                if (constructor.getParameterTypes()[i] == String.class && properties != null) {
                    if (!serviceUrls.path(property).isTextual() || serviceUrls.path(property).asText().isBlank())
                        throw new IllegalArgumentException("Missing operation service URL binding");
                    arguments[i] = serviceUrls.path(property).asText();
                } else arguments[i] = construct(constructor.getParameterTypes()[i], constructing);
            }
            return constructor.newInstance(arguments);
        } finally { constructing.remove(type); }
    }
}
