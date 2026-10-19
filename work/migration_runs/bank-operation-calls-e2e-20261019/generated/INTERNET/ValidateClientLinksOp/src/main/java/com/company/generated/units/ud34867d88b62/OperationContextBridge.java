package com.company.generated.units.ud34867d88b62;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public class OperationContextBridge {
    private final Map<String, Object> values = new HashMap<>();

    public Object getValueAt(String name) {
        return values.get(Objects.requireNonNull(name, "Context field name"));
    }

    public void setValueAt(String name, Object value) {
        values.put(Objects.requireNonNull(name, "Context field name"), value);
    }
}