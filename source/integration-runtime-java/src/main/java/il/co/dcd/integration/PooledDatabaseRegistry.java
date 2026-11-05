package il.co.dcd.integration;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.util.Map;
import java.util.LinkedHashMap;
import javax.sql.DataSource;

/** Owns one lazily connected pool for the selected database in this application process. */
public final class PooledDatabaseRegistry implements DatabaseRegistry, AutoCloseable {
    private final Map<String, HikariDataSource> pools = new LinkedHashMap<>();

    public PooledDatabaseRegistry(NativeRuntimeProperties properties) {
        String name = properties.getOperation().getDatabase();
        if (name == null || name.isBlank()) return;
        NativeRuntimeProperties.Database database = properties.getDatabases().get(name);
        if (database == null) throw new IllegalArgumentException("Unknown configured database: " + name);
        if (database.getJdbcUrl() == null || database.getJdbcUrl().isBlank())
            throw new IllegalArgumentException("Missing JDBC URL for database: " + name);
        HikariConfig config = new HikariConfig();
        config.setPoolName("native-" + name);
        config.setJdbcUrl(database.getJdbcUrl());
        if (database.getDriverClass() != null && !database.getDriverClass().isBlank())
            config.setDriverClassName(database.getDriverClass());
        config.setUsername(database.getUsername()); config.setPassword(database.getPassword());
        config.setMinimumIdle(database.getMinimumIdle()); config.setMaximumPoolSize(database.getMaximumPoolSize());
        config.setConnectionTimeout(database.getConnectionTimeoutMs()); config.setMaxLifetime(database.getMaxLifetimeMs());
        config.setInitializationFailTimeout(-1);
        pools.put(name, new HikariDataSource(config));
    }

    @Override public DataSource resolve(String name) {
        DataSource result = pools.get(name);
        if (result == null) throw new IllegalArgumentException("Unknown configured database: " + name);
        return result;
    }
    @Override public void close() { pools.values().forEach(HikariDataSource::close); }
}
