package com.ibm.dse.base;

import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/** Demo operation context containing named values and an externally supplied JDBC connection. */
public class Context {
    private final Map<String, Object> values = new HashMap<>();
    private Connection connection;

    public Object getValueAt(String name) {
        return values.get(Objects.requireNonNull(name, "Context field name"));
    }

    public void setValueAt(String name, Object value) {
        values.put(Objects.requireNonNull(name, "Context field name"), value);
    }

    /** Isolate a collection row while retaining runtime settings and the caller's connection. */
    public Context copyWith(Map<String, ?> row) {
        Context copy = new Context();
        copy.values.putAll(values);
        copy.values.putAll(row);
        copy.connection = connection;
        return copy;
    }

    public Map<String, Object> snapshot() { return new HashMap<>(values); }

    /** The caller owns the connection and its transaction lifecycle. */
    public void setConnection(Connection connection) {
        this.connection = Objects.requireNonNull(connection, "JDBC connection");
    }

    public Connection getConnection() {
        if (connection == null) {
            throw new IllegalStateException("Configure a JDBC connection before executing a database step");
        }
        return connection;
    }
}
