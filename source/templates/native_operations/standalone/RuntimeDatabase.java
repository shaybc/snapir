// JDBC configuration belongs to the launcher, never to generated business logic.
import com.fasterxml.jackson.databind.JsonNode;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.logging.Logger;
import javax.sql.DataSource;
import java.io.PrintWriter;

final class RuntimeDatabase implements DataSource {
    private final JsonNode settings;

    RuntimeDatabase(JsonNode root, String name) {
        settings = root.path("databases").path(name);
    }

    @Override
    public Connection getConnection() throws SQLException {
        return getConnection(settings.path("user").asText(), settings.path("password").asText());
    }

    @Override
    public Connection getConnection(String user, String password) throws SQLException {
        String url = settings.path("jdbc_url").asText();
        if (url.isBlank()) throw new SQLException("Configure databases.<name>.jdbc_url in runtime-config.json");
        for (String key : new String[]{"ip", "port", "schema"}) {
            String marker = "{" + key + "}";
            if (url.contains(marker)) {
                if (settings.path(key).isNull() || settings.path(key).asText().isBlank())
                    throw new SQLException("Missing database setting: " + key);
                url = url.replace(marker, settings.path(key).asText());
            }
        }
        String driver = settings.path("driver_class").asText();
        if (!driver.isBlank()) {
            try { Class.forName(driver); }
            catch (ClassNotFoundException e) {
                throw new SQLException("JDBC driver unavailable; place its JAR in the shared lib folder", e);
            }
        }
        return DriverManager.getConnection(url, user, password);
    }

    @Override public PrintWriter getLogWriter() { return null; }
    @Override public void setLogWriter(PrintWriter writer) { }
    @Override public void setLoginTimeout(int seconds) { DriverManager.setLoginTimeout(seconds); }
    @Override public int getLoginTimeout() { return DriverManager.getLoginTimeout(); }
    @Override public Logger getParentLogger() { return Logger.getLogger("standalone.jdbc"); }
    @Override public boolean isWrapperFor(Class<?> type) { return type.isInstance(this); }
    @Override public <T> T unwrap(Class<T> type) throws SQLException {
        if (type.isInstance(this)) return type.cast(this);
        throw new SQLException("Unsupported DataSource wrapper");
    }
}
