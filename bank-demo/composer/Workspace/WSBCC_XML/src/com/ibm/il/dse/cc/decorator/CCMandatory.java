package com.ibm.il.dse.cc.decorator;

import com.ibm.dse.base.FormatDecoratorHolder;

/** Demo policy: reject null and empty strings in either direction; preserve whitespace. */
public class CCMandatory extends FormatDecoratorHolder {
    @Override
    public String addDecoration(String value) { return requireValue(value); }

    @Override
    public String removeDecoration(String value) { return requireValue(value); }

    private String requireValue(String value) {
        if (value == null || value.isEmpty()) {
            throw new IllegalArgumentException("Mandatory value is missing");
        }
        return value;
    }
}
