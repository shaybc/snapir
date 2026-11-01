package com.ibm.dse.base;

import java.util.Map;

/** Demo configured step: its source attributes and executable implementation. */
public class KeyedCollection extends Tag {
    private final CCOperationStep implementation;

    public KeyedCollection(Map<String, String> attributes, CCOperationStep implementation) {
        super(attributes);
        this.implementation = implementation;
    }

    public CCOperationStep getImplementation() { return implementation; }
}
