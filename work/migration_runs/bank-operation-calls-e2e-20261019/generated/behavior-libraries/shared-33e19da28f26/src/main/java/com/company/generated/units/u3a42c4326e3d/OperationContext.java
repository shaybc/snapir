package com.company.generated.units.u3a42c4326e3d;

import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public class OperationContext {
    private final Map<String, Object> values = new HashMap<>();
    private Connection connection;

    public Object getValueAt(String name) {
        return values.get(Objects.requireNonNull(name, "Context field name"));
    }

    public void setValueAt(String name, Object value) {
        values.put(Objects.requireNonNull(name, "Context field name"), value);
    }

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