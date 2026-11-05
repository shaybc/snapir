package il.co.dcd.integration;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Spring binds infrastructure properties; business initialization keys remain exact JSON keys. */
@ConfigurationProperties("native-runtime")
public class NativeRuntimeProperties {
    private Operation operation = new Operation();
    private Map<String, Database> databases = new LinkedHashMap<>();
    private String initializationFile = "classpath:operation-initialization.json";
    public Operation getOperation() { return operation; }
    public void setOperation(Operation value) { operation = value; }
    public Map<String, Database> getDatabases() { return databases; }
    public void setDatabases(Map<String, Database> value) { databases = value; }
    public String getInitializationFile() { return initializationFile; }
    public void setInitializationFile(String value) { initializationFile = value; }

    /** Each service selects its named database independently of request data. */
    public static class Operation {
        private String identity;
        private String database = "default";
        public String getIdentity() { return identity; }
        public void setIdentity(String value) { identity = value; }
        public String getDatabase() { return database; }
        public void setDatabase(String value) { database = value; }
    }

    /** A named pool's secret-backed connection settings and bounded capacity. */
    public static class Database {
        private String jdbcUrl, driverClass, username, password;
        private int minimumIdle = 0, maximumPoolSize = 10;
        private long connectionTimeoutMs = 30000, maxLifetimeMs = 1800000;
        public String getJdbcUrl() { return jdbcUrl; } public void setJdbcUrl(String v) { jdbcUrl = v; }
        public String getDriverClass() { return driverClass; } public void setDriverClass(String v) { driverClass = v; }
        public String getUsername() { return username; } public void setUsername(String v) { username = v; }
        public String getPassword() { return password; } public void setPassword(String v) { password = v; }
        public int getMinimumIdle() { return minimumIdle; } public void setMinimumIdle(int v) { minimumIdle = v; }
        public int getMaximumPoolSize() { return maximumPoolSize; } public void setMaximumPoolSize(int v) { maximumPoolSize = v; }
        public long getConnectionTimeoutMs() { return connectionTimeoutMs; } public void setConnectionTimeoutMs(long v) { connectionTimeoutMs = v; }
        public long getMaxLifetimeMs() { return maxLifetimeMs; } public void setMaxLifetimeMs(long v) { maxLifetimeMs = v; }
    }
}
