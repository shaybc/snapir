package com.company.generated;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/** Demo step contract with a shared operation context and explicitly registered services. */
public abstract class CCOperationStep {
    private Context context;
    private final Map<String, Object> services = new HashMap<>();

    public abstract int execute() throws Exception;

    public void setContext(Context context) {
        this.context = Objects.requireNonNull(context, "Operation context");
    }

    public Context getContext() {
        if (context == null) {
            throw new IllegalStateException("Configure an operation context before executing a step");
        }
        return context;
    }

    public void setService(String name, Object service) {
        services.put(Objects.requireNonNull(name, "Service name"), Objects.requireNonNull(service, "Service"));
    }

    public Object getService(String name) {
        Object service = services.get(Objects.requireNonNull(name, "Service name"));
        if (service == null) {
            throw new IllegalStateException("Configure the named service before executing a step: " + name);
        }
        return service;
    }
}