package com.company.generated;

import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import javax.sql.DataSource;

/** Demo operation context containing named values and an externally supplied JDBC connection or DataSource. */
public class Context {
    private final Map<String, Object> values = new HashMap<>();
    private Connection connection;
    private final DataSource dataSource;

    public Context() {
        this.dataSource = null;
    }

    public Context(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public Object getValueAt(String name) {
        return values.get(Objects.requireNonNull(name, "Context field name"));
    }

    public void setValueAt(String name, Object value) {
        values.put(Objects.requireNonNull(name, "Context field name"), value);
    }

    /** The caller owns the connection and its transaction lifecycle. */
    public void setConnection(Connection connection) {
        this.connection = Objects.requireNonNull(connection, "JDBC connection");
    }

    public Connection getConnection() throws java.sql.SQLException {
        if (connection != null) {
            return connection;
        }
        if (dataSource != null) {
            return dataSource.getConnection();
        }
        throw new IllegalStateException("Configure a JDBC connection or DataSource before executing a database step");
    }
}
