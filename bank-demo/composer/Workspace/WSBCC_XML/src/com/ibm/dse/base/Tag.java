package com.ibm.dse.base;

import java.util.HashMap;
import java.util.Map;

/** Minimal demo configuration tag containing string attributes. */
public class Tag {
    private final Map<String, String> attributes = new HashMap<>();

    public Tag() {
    }

    public Tag(Map<String, String> attributes) {
        this.attributes.putAll(attributes);
    }

    public String getAttribute(String name) {
        return attributes.get(name);
    }

    public void setAttribute(String name, String value) {
        attributes.put(name, value);
    }
}
